import re
import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from .config import DatabaseConfig


class PermissionError(Exception):
    """数据库连接无此操作权限。"""


class SQLSafetyError(Exception):
    """SQL 语句类型与调用的工具不匹配，或包含危险操作。"""


_DIALECTS = {"mysql": "mysql", "postgresql": "postgres"}

_WRITE_TYPES = (exp.Insert, exp.Update, exp.Delete, exp.Merge)
_DDL_TYPES = (exp.Create, exp.Drop, exp.Alter, exp.TruncateTable, exp.Comment)
# sqlglot 不认识的语法会退化为 Command，this 为首个关键字
_DDL_COMMANDS = {"CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME", "COMMENT"}
# 出现在只读查询任意位置都视为修改（含 PG 的数据修改 CTE、SELECT INTO）
_MODIFYING = _WRITE_TYPES + _DDL_TYPES + (exp.Command, exp.Into)
# MySQL 会执行 /*! */ 里的内容，sqlglot 视为注释，二者理解不一致可藏入多条语句；
# /*+ */ 优化器提示可覆盖 max_execution_time
_RE_MYSQL_SPECIAL_COMMENT = re.compile(r"/\*(M?!|\+)")


def _parse_one(config: DatabaseConfig, sql: str) -> exp.Expression:
    """解析 SQL，确保恰好一条语句。"""
    if config.type == "mysql" and _RE_MYSQL_SPECIAL_COMMENT.search(sql):
        raise SQLSafetyError("不允许使用 MySQL 可执行注释 /*! */ 或优化器提示 /*+ */")
    try:
        statements = sqlglot.parse(sql, read=_DIALECTS[config.type])
    except SqlglotError as e:
        raise SQLSafetyError(f"SQL 解析失败: {e}")
    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SQLSafetyError(f"一次只能执行一条 SQL 语句，收到 {len(statements)} 条")
    return statements[0]


def _command(stmt: exp.Expression) -> str:
    return str(stmt.this).upper() if isinstance(stmt, exp.Command) else ""


def check_read_permission(config: DatabaseConfig, sql: str) -> None:
    """确认连接有读权限，且 SQL 是单条只读 SELECT。"""
    if not config.permissions.allow_read:
        raise PermissionError("此连接没有读权限（allow_read=false）")
    stmt = _parse_one(config, sql)
    if not isinstance(stmt, exp.Query) or any(
        isinstance(node, _MODIFYING) for node in stmt.walk()
    ):
        raise SQLSafetyError(
            f"execute_query 只允许只读 SELECT 语句。收到: {sql[:60]!r}"
        )


def check_write_permission(config: DatabaseConfig, sql: str) -> None:
    """确认连接有写权限，且 SQL 是单条 DML；UPDATE/DELETE 必须带 WHERE。"""
    if not config.permissions.allow_write:
        raise PermissionError("此连接没有写权限（allow_write=false）")
    stmt = _parse_one(config, sql)
    if _command(stmt) == "REPLACE":  # MySQL REPLACE INTO，sqlglot 不解析
        return
    if not isinstance(stmt, _WRITE_TYPES) or any(
        isinstance(node, _DDL_TYPES + (exp.Command,)) for node in stmt.walk()
    ):
        raise SQLSafetyError(
            f"execute_write 只允许 INSERT/UPDATE/DELETE/REPLACE/MERGE。收到: {sql[:60]!r}"
        )
    # PG 数据修改 CTE 会绕过 WHERE 检查和影响行数统计
    if any(isinstance(n, _WRITE_TYPES) for cte in stmt.find_all(exp.CTE) for n in cte.walk()):
        raise SQLSafetyError("WITH 子句中不允许 INSERT/UPDATE/DELETE")
    if isinstance(stmt, (exp.Update, exp.Delete)) and not stmt.args.get("where"):
        raise SQLSafetyError("UPDATE/DELETE 必须带 WHERE 条件")


def check_ddl_permission(config: DatabaseConfig, sql: str) -> None:
    """确认连接有 DDL 权限，且 SQL 是单条 DDL 语句。"""
    if not config.permissions.allow_ddl:
        raise PermissionError("此连接没有 DDL 权限（allow_ddl=false）")
    stmt = _parse_one(config, sql)
    if not isinstance(stmt, _DDL_TYPES) and _command(stmt) not in _DDL_COMMANDS:
        raise SQLSafetyError(
            f"execute_ddl 只允许 CREATE/ALTER/DROP/TRUNCATE 等 DDL 语句。收到: {sql[:60]!r}"
        )


def validate_identifier(name: str) -> None:
    """校验表名/列名等 SQL 标识符，只允许字母、数字、下划线、连字符。"""
    if not re.match(r"^[a-zA-Z0-9_\-]+$", name):
        raise ValueError(f"无效的标识符: {name!r}（只允许字母、数字、_ 和 -）")
