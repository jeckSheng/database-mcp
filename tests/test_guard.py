import pytest
from database_mcp.config import DatabaseConfig, Permissions
from database_mcp.guard import (
    check_read_permission,
    check_write_permission,
    check_ddl_permission,
    PermissionError,
    SQLSafetyError,
)


def make_config(
    allow_read=True, allow_write=False, allow_ddl=False, db_type="mysql"
) -> DatabaseConfig:
    return DatabaseConfig(
        type=db_type,
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


# --- 多语句 / 绕过 / 防误操作 ---

@pytest.mark.parametrize("sql", [
    "SELECT 1; DROP TABLE users;",
    "SELECT 1; DROP TABLE users",
    "/* x */ DROP TABLE users",
    "SELECT * FROM t INTO OUTFILE '/tmp/x'",
    "SELECT a INTO @v FROM t",
    "SELECT 1 /*! ,'*/' */ ; DROP TABLE t2; -- '",
    "SELECT * FROM t /*! INTO OUTFILE '/tmp/x' */",
    "SELECT /*+ MAX_EXECUTION_TIME(99999) */ SLEEP(3)",
])
def test_read_blocks_bypass_mysql(sql):
    with pytest.raises(SQLSafetyError):
        check_read_permission(make_config(), sql)


@pytest.mark.parametrize("sql", [
    "WITH d AS (DELETE FROM t RETURNING *) SELECT * FROM d",
    "SELECT * INTO newt FROM t",
])
def test_read_blocks_bypass_pg(sql):
    with pytest.raises(SQLSafetyError):
        check_read_permission(make_config(db_type="postgresql"), sql)


@pytest.mark.parametrize("sql", [
    "SELECT ';' AS a FROM t -- ; DROP TABLE t",
    "SELECT 1;",
    "WITH a AS (SELECT 1 AS x) SELECT * FROM a",
    "(SELECT 1) UNION (SELECT 2)",
    "SELECT * FROM t WHERE name LIKE 'a%'",
])
def test_read_allows_valid_select(sql):
    check_read_permission(make_config(), sql)


def test_read_blocks_unparseable():
    with pytest.raises(SQLSafetyError):
        check_read_permission(make_config(), "SELEC 1")


def test_write_blocks_multi_statement_pg():
    with pytest.raises(SQLSafetyError):
        check_write_permission(
            make_config(allow_write=True, db_type="postgresql"),
            "INSERT INTO t VALUES (1); DROP TABLE x;",
        )


@pytest.mark.parametrize("sql", [
    "UPDATE t SET x=1",
    "DELETE FROM t",
    "DELETE t1 FROM t1 JOIN t2 ON t1.id=t2.id",
])
def test_write_blocks_without_where(sql):
    with pytest.raises(SQLSafetyError, match="WHERE"):
        check_write_permission(make_config(allow_write=True), sql)


def test_write_allows_replace():
    check_write_permission(make_config(allow_write=True), "REPLACE INTO t (a) VALUES (1)")


def test_ddl_blocks_multi_statement():
    with pytest.raises(SQLSafetyError):
        check_ddl_permission(make_config(allow_ddl=True), "CREATE TABLE a (id INT); DROP TABLE b")


@pytest.mark.parametrize("sql", ["RENAME TABLE a TO b", "COMMENT ON TABLE t IS 'x'"])
def test_ddl_allows_rename_comment(sql):
    db_type = "postgresql" if sql.startswith("COMMENT") else "mysql"
    check_ddl_permission(make_config(allow_ddl=True, db_type=db_type), sql)


def test_write_blocks_executable_comment_mysql():
    with pytest.raises(SQLSafetyError):
        check_write_permission(
            make_config(allow_write=True),
            "UPDATE t SET a=7 WHERE id = /*! 1 AND '' <> '*/' */ ; DROP TABLE t3; -- '",
        )


@pytest.mark.parametrize("sql", [
    "WITH d AS (DELETE FROM users RETURNING id) UPDATE t SET x=1 WHERE id=0",
    "WITH d AS (DELETE FROM users RETURNING *) INSERT INTO log SELECT * FROM d",
])
def test_write_blocks_modifying_cte_pg(sql):
    with pytest.raises(SQLSafetyError, match="WITH"):
        check_write_permission(make_config(allow_write=True, db_type="postgresql"), sql)


@pytest.mark.parametrize("sql", [
    "MERGE INTO t USING s ON t.id=s.id WHEN MATCHED THEN UPDATE SET a=1 WHEN NOT MATCHED THEN INSERT (id) VALUES (s.id)",
    "WITH s AS (SELECT 1 AS id) UPDATE t SET x=1 FROM s WHERE t.id=s.id",
    "INSERT INTO t VALUES (1) ON CONFLICT (id) DO UPDATE SET a=2",
])
def test_write_allows_valid_pg(sql):
    check_write_permission(make_config(allow_write=True, db_type="postgresql"), sql)
