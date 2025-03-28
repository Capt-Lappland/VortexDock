# -*- coding: utf-8 -*-

import os
import ssl
import json
import socket
import queue
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from .logger import logger

class SSLContextManager:
    def __init__(self, cert_dir: str = 'certs'):
        self.cert_dir = Path(cert_dir)
        self.cert_dir.mkdir(exist_ok=True)
        self.cert_path = self.cert_dir / 'server.crt'
        self.key_path = self.cert_dir / 'server.key'
    
    def create_self_signed_cert(self):
        """Create a self-signed certificate"""
        if not self.cert_path.exists() or not self.key_path.exists():
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            import datetime
            
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )
            
            # Create certificate
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, u"VortexDock")
            ])
            
            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.datetime.utcnow()
            ).not_valid_after(
                datetime.datetime.utcnow() + datetime.timedelta(days=365)
            ).sign(private_key, hashes.SHA256())
            
            # Save certificate and private key
            with open(self.cert_path, 'wb') as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            
            with open(self.key_path, 'wb') as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
    
    def get_server_context(self) -> ssl.SSLContext:
        """Get server SSL context"""
        self.create_self_signed_cert()
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=str(self.cert_path), keyfile=str(self.key_path))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_3
        context.set_ciphers('ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256')
        return context
    
    def get_client_context(self) -> ssl.SSLContext:
        """Get client SSL context"""
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        if self.cert_path.exists():
            context.load_verify_locations(str(self.cert_path))
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE  # Use self-signed certificate in development environment
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_3
        context.set_ciphers('ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256')
        return context

class ConnectionPool:
    def __init__(self, pool_size: int = 5):
        self.pool_size = pool_size
        self.pool = queue.Queue(pool_size)
        self.lock = threading.Lock()
        self.active_connections = set()
    
    def get_connection(self, create_func) -> socket.socket:
        """Get a connection, create a new one if no available connection exists"""
        try:
            conn = self.pool.get_nowait()
            if self._is_connection_valid(conn):
                return conn
            self._close_connection(conn)
        except queue.Empty:
            pass
        
        with self.lock:
            if len(self.active_connections) < self.pool_size:
                conn = create_func()
                self.active_connections.add(conn)
                return conn
            raise ConnectionError("Connection pool is full")
    
    def return_connection(self, conn: socket.socket):
        """Return a connection to the connection pool"""
        if conn in self.active_connections:
            try:
                self.pool.put_nowait(conn)
            except queue.Full:
                self._close_connection(conn)
    
    def _is_connection_valid(self, conn: socket.socket) -> bool:
        """Check if the connection is valid"""
        try:
            # Send heartbeat check
            conn.send(json.dumps({'type': 'heartbeat'}).encode())
            response = conn.recv(1024)
            return bool(response)
        except:
            return False
    
    def _close_connection(self, conn: socket.socket):
        """Close the connection"""
        try:
            conn.close()
        except:
            pass
        self.active_connections.discard(conn)
    
    def close_all(self):
        """Close all connections"""
        with self.lock:
            while not self.pool.empty():
                try:
                    conn = self.pool.get_nowait()
                    self._close_connection(conn)
                except queue.Empty:
                    break
            
            for conn in list(self.active_connections):
                self._close_connection(conn)

class SecureSocket:
    def __init__(self, sock: socket.socket, ssl_context: ssl.SSLContext):
        # Choose the correct wrapping method based on the SSL context type
        if ssl_context.protocol == ssl.PROTOCOL_TLS_SERVER:
            self.sock = ssl_context.wrap_socket(sock, server_side=True)
        else:
            self.sock = ssl_context.wrap_socket(sock)
        self._recv_buffer = b''
        self._send_buffer = b''
    
    def send_message(self, data: Dict[str, Any]):
        """Send a message, automatically handle encoding and fragmentation"""
        try:
            # Ensure all string values are UTF-8 encoded
            def encode_strings(obj):
                if isinstance(obj, str):
                    return obj.encode('utf-8', errors='strict').decode('utf-8')
                elif isinstance(obj, dict):
                    return {k: encode_strings(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [encode_strings(item) for item in obj]
                return obj
            
            encoded_data = encode_strings(data)
            message = json.dumps(encoded_data, ensure_ascii=True).encode('utf-8')
            length = len(message)
            header = length.to_bytes(4, byteorder='big')
            self.sock.sendall(header + message)
        except UnicodeEncodeError as e:
            logger.error(f"Encoding error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise
    
    def receive_message(self) -> Optional[Dict[str, Any]]:
        """Receive a message, automatically handle decoding and fragmentation"""
        try:
            # Read the message length
            header = self._recv_exactly(4)
            if not header:
                return None
            length = int.from_bytes(header, byteorder='big')
            
            # Read the message content
            message = self._recv_exactly(length)
            if not message:
                return None
            
            try:
                # Try decoding directly
                decoded_message = message.decode('utf-8', errors='strict')
            except UnicodeDecodeError:
                # If it fails, try using latin1 encoding (preserve raw bytes)
                decoded_message = message.decode('latin1')
            
            return json.loads(decoded_message)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decoding error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            raise
    
    def _recv_exactly(self, n: int) -> Optional[bytes]:
        """Receive exactly the specified number of bytes"""
        while len(self._recv_buffer) < n:
            chunk = self.sock.recv(4096)
            if not chunk:
                return None
            self._recv_buffer += chunk
        
        result = self._recv_buffer[:n]
        self._recv_buffer = self._recv_buffer[n:]
        return result
    
    def close(self):
        """Close the connection"""
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except:
            pass
        try:
            self.sock.close()
        except:
            pass