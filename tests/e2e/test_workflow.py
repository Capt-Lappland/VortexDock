import subprocess
import time
import pytest
from pathlib import Path

SAMPLE_ZIP = "tests/data/sample_task.zip"

def test_full_workflow(tmp_path):
    """完整流程测试：创建任务->处理->获取结果"""
    # 1. 创建测试任务
    cp_result = subprocess.run(
        ["python", "./compute_node/cli.py", "-zip", SAMPLE_ZIP, "-name", "e2e_test"],
        capture_output=True,
        text=True
    )
    assert "成功创建任务" in cp_result.stdout
    
    # 2. 启动服务端
    server_proc = subprocess.Popen(["python", "server.py"])
    time.sleep(2)  # 等待服务启动
    
    try:
        # 3. 启动客户端处理
        client_proc = subprocess.Popen(["python", "client.py"])
        time.sleep(20)  # 等待任务处理
        
        # 4. 验证任务状态
        ls_result = subprocess.run(
            ["python", "cli.py", "-ls"],
            capture_output=True,
            text=True
        )
        assert "e2e_test" in ls_result.stdout
        assert "completed" in ls_result.stdout
        
        # 5. 验证结果文件
        result_file = Path("results/e2e_test/lig1_out.pdbqt")
        assert result_file.exists()
        assert result_file.stat().st_size > 1024
        
    finally:
        server_proc.terminate()
        client_proc.terminate()