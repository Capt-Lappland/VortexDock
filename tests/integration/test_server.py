import pytest
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from server import check_timeout_tasks

class MockRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()

@pytest.fixture(scope="module")
def mock_http_server():
    """启动模拟HTTP服务器"""
    server = HTTPServer(('localhost', 9000), MockRequestHandler)
    thread = Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    yield server
    server.shutdown()

def test_timeout_task_reset(mock_db):
    """验证超时任务重置逻辑"""
    # 准备测试数据
    execute_update("INSERT INTO tasks (id, status) VALUES ('test_task', 'processing')")
    execute_update("""
        CREATE TABLE IF NOT EXISTS task_test_task_ligands (
            ligand_id VARCHAR(255) PRIMARY KEY,
            status VARCHAR(50),
            last_updated TIMESTAMP
        )
    """)
    execute_update("""
        INSERT INTO task_test_task_ligands 
        (ligand_id, status, last_updated)
        VALUES ('lig1', 'processing', NOW() - INTERVAL 2 HOUR)
    """)
    
    # 执行超时检查
    check_timeout_tasks()
    
    # 验证状态更新
    result = execute_query(
        "SELECT status FROM task_test_task_ligands WHERE ligand_id='lig1'",
        fetch_one=True
    )
    assert result['status'] == 'pending'