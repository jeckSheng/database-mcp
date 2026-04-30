import pytest
from unittest.mock import MagicMock
from database_mcp.config import AppConfig, DatabaseConfig, Permissions
from database_mcp.router import Router


def make_app_config() -> AppConfig:
    return AppConfig(
        databases={
            "mysql_ro": DatabaseConfig(
                type="mysql",
                host="localhost",
                port=3306,
                database="db1",
                user="user",
                password="pass",
                permissions=Permissions(allow_read=True, allow_write=False, allow_ddl=False),
            ),
            "pg_rw": DatabaseConfig(
                type="postgresql",
                host="localhost",
                port=5432,
                database="db2",
                user="user",
                password="pass",
                permissions=Permissions(allow_read=True, allow_write=True, allow_ddl=False),
            ),
        }
    )


def test_get_pool_returns_correct_pool():
    config = make_app_config()
    pool_a, pool_b = MagicMock(), MagicMock()
    router = Router(config, {"mysql_ro": pool_a, "pg_rw": pool_b})
    assert router.get_pool("mysql_ro") is pool_a
    assert router.get_pool("pg_rw") is pool_b


def test_get_pool_raises_for_unknown():
    config = make_app_config()
    router = Router(config, {"mysql_ro": MagicMock()})
    with pytest.raises(KeyError, match="unknown_conn"):
        router.get_pool("unknown_conn")


def test_get_config_returns_correct_config():
    config = make_app_config()
    router = Router(config, {})
    db_cfg = router.get_config("mysql_ro")
    assert db_cfg.type == "mysql"
    assert db_cfg.permissions.allow_write is False


def test_get_config_raises_for_unknown():
    config = make_app_config()
    router = Router(config, {})
    with pytest.raises(KeyError, match="no_such_db"):
        router.get_config("no_such_db")


def test_list_connections_returns_all_names():
    config = make_app_config()
    router = Router(config, {})
    connections = router.list_connections()
    names = [c["name"] for c in connections]
    assert "mysql_ro" in names
    assert "pg_rw" in names


def test_list_connections_includes_type_and_database():
    config = make_app_config()
    router = Router(config, {})
    connections = router.list_connections()
    mysql_conn = next(c for c in connections if c["name"] == "mysql_ro")
    assert mysql_conn["type"] == "mysql"
    assert mysql_conn["database"] == "db1"


def test_list_connections_includes_permissions():
    config = make_app_config()
    router = Router(config, {})
    connections = router.list_connections()
    mysql_conn = next(c for c in connections if c["name"] == "mysql_ro")
    assert mysql_conn["permissions"]["allow_read"] is True
    assert mysql_conn["permissions"]["allow_write"] is False
    assert mysql_conn["permissions"]["allow_ddl"] is False


def test_list_connections_does_not_expose_password():
    config = make_app_config()
    router = Router(config, {})
    connections = router.list_connections()
    for conn in connections:
        assert "password" not in conn
