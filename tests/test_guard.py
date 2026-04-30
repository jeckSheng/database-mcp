import pytest
from database_mcp.config import DatabaseConfig, Permissions
from database_mcp.guard import (
    check_read_permission,
    check_write_permission,
    check_ddl_permission,
    PermissionError,
    SQLSafetyError,
)


def make_config(allow_read=True, allow_write=False, allow_ddl=False) -> DatabaseConfig:
    return DatabaseConfig(
        type="mysql",
        host="localhost",
        port=3306,
        database="test",
        user="root",
        password="secret",
        permissions=Permissions(
            allow_read=allow_read,
            allow_write=allow_write,
            allow_ddl=allow_ddl,
        ),
    )


# --- check_read_permission ---

def test_read_allows_select():
    check_read_permission(make_config(allow_read=True), "SELECT * FROM users")


def test_read_allows_select_with_whitespace():
    check_read_permission(make_config(allow_read=True), "  SELECT id FROM orders WHERE id=1")


def test_read_blocks_insert():
    with pytest.raises(SQLSafetyError):
        check_read_permission(make_config(allow_read=True), "INSERT INTO users VALUES (1)")


def test_read_blocks_update():
    with pytest.raises(SQLSafetyError):
        check_read_permission(make_config(allow_read=True), "UPDATE users SET name='x'")


def test_read_blocks_drop():
    with pytest.raises(SQLSafetyError):
        check_read_permission(make_config(allow_read=True), "DROP TABLE users")


def test_read_blocks_when_no_permission():
    with pytest.raises(PermissionError):
        check_read_permission(make_config(allow_read=False), "SELECT 1")


# --- check_write_permission ---

def test_write_allows_insert():
    check_write_permission(
        make_config(allow_write=True),
        "INSERT INTO users (name) VALUES ('Alice')",
    )


def test_write_allows_update():
    check_write_permission(
        make_config(allow_write=True),
        "UPDATE users SET name='Bob' WHERE id=1",
    )


def test_write_allows_delete():
    check_write_permission(
        make_config(allow_write=True),
        "DELETE FROM users WHERE id=1",
    )


def test_write_blocks_drop():
    with pytest.raises(SQLSafetyError):
        check_write_permission(make_config(allow_write=True), "DROP TABLE users")


def test_write_blocks_truncate():
    with pytest.raises(SQLSafetyError):
        check_write_permission(make_config(allow_write=True), "TRUNCATE TABLE users")


def test_write_blocks_select():
    with pytest.raises(SQLSafetyError):
        check_write_permission(make_config(allow_write=True), "SELECT * FROM users")


def test_write_blocks_create():
    with pytest.raises(SQLSafetyError):
        check_write_permission(make_config(allow_write=True), "CREATE TABLE foo (id INT)")


def test_write_blocks_when_no_permission():
    with pytest.raises(PermissionError):
        check_write_permission(
            make_config(allow_write=False), "INSERT INTO users VALUES (1)"
        )


# --- check_ddl_permission ---

def test_ddl_allows_create():
    check_ddl_permission(
        make_config(allow_ddl=True), "CREATE TABLE foo (id INT PRIMARY KEY)"
    )


def test_ddl_allows_drop():
    check_ddl_permission(make_config(allow_ddl=True), "DROP TABLE foo")


def test_ddl_allows_alter():
    check_ddl_permission(
        make_config(allow_ddl=True), "ALTER TABLE foo ADD COLUMN bar TEXT"
    )


def test_ddl_allows_truncate():
    check_ddl_permission(make_config(allow_ddl=True), "TRUNCATE TABLE foo")


def test_ddl_blocks_select():
    with pytest.raises(SQLSafetyError):
        check_ddl_permission(make_config(allow_ddl=True), "SELECT * FROM users")


def test_ddl_blocks_insert():
    with pytest.raises(SQLSafetyError):
        check_ddl_permission(
            make_config(allow_ddl=True), "INSERT INTO users VALUES (1)"
        )


def test_ddl_blocks_when_no_permission():
    with pytest.raises(PermissionError):
        check_ddl_permission(
            make_config(allow_ddl=False), "CREATE TABLE foo (id INT)"
        )
