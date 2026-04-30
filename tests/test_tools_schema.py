import json
import pytest
from unittest.mock import AsyncMock
from database_mcp.config import AppConfig, DatabaseConfig, Permissions
from database_mcp.router import Router
from database_mcp.tools.schema import list_connections, list_tables, describe_table
from database_mcp.guard import PermissionError


def make_router(allow_read=True) -> tuple:
    config = AppConfig(
        databases={
            "testdb": DatabaseConfig(
                type="mysql",
                host="host-a",
                port=3306,
                database="db1",
                user="u",
                password="p",
                permissions=Permissions(
                    allow_read=allow_read, allow_write=False, allow_ddl=False
                ),
            ),
            "pgdb": DatabaseConfig(
                type="postgresql",
                host="host-b",
                port=5432,
                database="db2",
                user="u",
                password="p",
                permissions=Permissions(
                    allow_read=True, allow_write=True, allow_ddl=False
                ),
            ),
        }
    )
    mock_pool = AsyncMock()
    mock_pool_pg = AsyncMock()
    return Router(config, {"testdb": mock_pool, "pgdb": mock_pool_pg}), mock_pool


async def test_list_connections_returns_all_names():
    router, _ = make_router()
    result = await list_connections(router)
    data = json.loads(result)
    names = [c["name"] for c in data]
    assert "testdb" in names
    assert "pgdb" in names


async def test_list_connections_includes_permissions():
    router, _ = make_router()
    result = await list_connections(router)
    data = json.loads(result)
    testdb = next(c for c in data if c["name"] == "testdb")
    assert testdb["permissions"]["allow_read"] is True
    assert testdb["permissions"]["allow_write"] is False


async def test_list_connections_excludes_password():
    router, _ = make_router()
    result = await list_connections(router)
    assert "password" not in result


async def test_list_tables_returns_table_names():
    router, mock_pool = make_router(allow_read=True)
    mock_pool.fetch_tables = AsyncMock(return_value=["users", "orders", "products"])
    result = await list_tables(router, "testdb")
    data = json.loads(result)
    assert "users" in data
    assert "orders" in data
    assert "products" in data


async def test_list_tables_rejects_no_read_permission():
    router, _ = make_router(allow_read=False)
    with pytest.raises(PermissionError):
        await list_tables(router, "testdb")


async def test_describe_table_returns_columns():
    router, mock_pool = make_router(allow_read=True)
    mock_pool.describe_table = AsyncMock(
        return_value=[
            {"Field": "id", "Type": "int", "Null": "NO", "Key": "PRI"},
            {"Field": "name", "Type": "varchar(255)", "Null": "YES", "Key": ""},
        ]
    )
    result = await describe_table(router, "testdb", "users")
    data = json.loads(result)
    assert len(data) == 2
    assert data[0]["Field"] == "id"
    assert data[1]["Type"] == "varchar(255)"


async def test_describe_table_rejects_sql_injection_in_table_name():
    router, _ = make_router(allow_read=True)
    with pytest.raises(ValueError, match="无效的标识符"):
        await describe_table(router, "testdb", "users; DROP TABLE users--")


async def test_describe_table_rejects_no_read_permission():
    router, _ = make_router(allow_read=False)
    with pytest.raises(PermissionError):
        await describe_table(router, "testdb", "users")
