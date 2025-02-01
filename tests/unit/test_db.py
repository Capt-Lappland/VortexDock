import pytest
from unittest.mock import MagicMock
from utils.db import execute_query, execute_update

@pytest.fixture
def mock_db(monkeypatch):
    """模拟数据库连接池"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    monkeypatch.setattr("utils.db.get_db_connection", lambda: mock_conn)
    return mock_conn, mock_cursor

def test_execute_query_success(mock_db):
    """测试查询语句执行成功"""
    mock_conn, mock_cursor = mock_db
    mock_cursor.fetchall.return_value = [{"id": 1, "status": "pending"}]
    
    result = execute_query("SELECT * FROM tasks")
    assert len(result) == 1
    mock_cursor.execute.assert_called_once_with("SELECT * FROM tasks", ())

def test_execute_update_retry(mock_db):
    """测试更新操作失败重试"""
    mock_conn, mock_cursor = mock_db
    mock_cursor.execute.side_effect = Exception("DB Error")
    
    with pytest.raises(Exception):
        execute_update("UPDATE tasks SET status='failed' WHERE id=1")
    assert mock_cursor.execute.call_count == 3  # 验证重试次数