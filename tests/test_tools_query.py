import json
import pytest
from unittest.mock import AsyncMock
from database_mcp.config import AppConfig, DatabaseConfig, Permissions
from database_mcp.router import Router
from database_mcp.tools.query import execute_query, execute_write, execute_ddl
from database_mcp.guard import PermissionError, SQLSafetyError


def make_router(
    allow_read=True, allow_write=False, allow_ddl=False
) -> tuple:
    config = AppConfig(
        databases={
            "testdb": DatabaseConfig(
                type="mysql",
                host="localhost",
                port=3306,
                database="db",
                user="u",
                password="p",
                permissions=Permissions(
                    allow_read=allow_read,
                    allow_write=allow_write,
                    allow_ddl=allow_ddl,
                ),
            )
        }
    )
    mock_pool = AsyncMock()
    return Router(config, {"testdb": mock_pool}), mock_pool


async def test_execute_query_returns_json():
    router, mock_pool = make_router(allow_read=True)
    mock_pool.fetch_all = AsyncMock(return_value=[{"id": 1, "name": "Alice"}])
    result = await execute_query(router, "testdb", "SELECT * FROM users")
    data = json.loads(result)
    assert data[0]["id"] == 1
    assert data[0]["name"] == "Alice"


async def test_execute_query_calls_fetch_all_with_sql():
    router, mock_pool = make_router(allow_read=True)
    mock_pool.fetch_all = AsyncMock(return_value=[])
    await execute_query(router, "testdb", "SELECT id FROM orders")
    mock_pool.fetch_all.assert_called_once_with("SELECT id FROM orders")


async def test_execute_query_rejects_insert():
    router, _ = make_router(allow_read=True)
    with pytest.raises(SQLSafetyError):
        await execute_query(router, "testdb", "INSERT INTO users VALUES (1)")


async def test_execute_query_rejects_no_read_permission():
    router, _ = make_router(allow_read=False)
    with pytest.raises(PermissionError):
        await execute_query(router, "testdb", "SELECT 1")


async def test_execute_write_returns_status():
    router, mock_pool = make_router(allow_write=True)
    mock_pool.execute = AsyncMock(return_value="1 row(s) affected")
    result = await execute_write(
        router, "testdb", "INSERT INTO users (name) VALUES ('Alice')"
    )
    assert "1 row(s) affected" in result


async def test_execute_write_calls_execute_with_sql():
    router, mock_pool = make_router(allow_write=True)
    mock_pool.execute = AsyncMock(return_value="1 row(s) affected")
    await execute_write(router, "testdb", "UPDATE users SET name='Bob' WHERE id=1")
    mock_pool.execute.assert_called_once_with("UPDATE users SET name='Bob' WHERE id=1")


async def test_execute_write_rejects_drop():
    router, _ = make_router(allow_write=True)
    with pytest.raises(SQLSafetyError):
        await execute_write(router, "testdb", "DROP TABLE users")


async def test_execute_write_rejects_truncate():
    router, _ = make_router(allow_write=True)
    with pytest.raises(SQLSafetyError):
        await execute_write(router, "testdb", "TRUNCATE TABLE users")


async def test_execute_write_rejects_no_write_permission():
    router, _ = make_router(allow_write=False)
    with pytest.raises(PermissionError):
        await execute_write(router, "testdb", "INSERT INTO users VALUES (1)")


async def test_execute_ddl_returns_status():
    router, mock_pool = make_router(allow_ddl=True)
    mock_pool.execute = AsyncMock(return_value="CREATE TABLE")
    result = await execute_ddl(
        router, "testdb", "CREATE TABLE foo (id INT PRIMARY KEY)"
    )
    assert "CREATE TABLE" in result


async def test_execute_ddl_rejects_select():
    router, _ = make_router(allow_ddl=True)
    with pytest.raises(SQLSafetyError):
        await execute_ddl(router, "testdb", "SELECT * FROM users")


async def test_execute_ddl_rejects_no_ddl_permission():
    router, _ = make_router(allow_ddl=False)
    with pytest.raises(PermissionError):
        await execute_ddl(router, "testdb", "CREATE TABLE foo (id INT)")
