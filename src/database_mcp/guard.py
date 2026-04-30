import re
from .config import DatabaseConfig


class PermissionError(Exception):
    """数据库连接无此操作权限。"""


class SQLSafetyError(Exception):
    """SQL 语句类型与调用的工具不匹配，或包含危险操作。"""


# 正则：按 SQL 语句首个关键字分类
_RE_SELECT = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_RE_WRITE = re.compile(r"^\s*(INSERT|UPDATE|DELETE|REPLACE|MERGE)\b", re.IGNORECASE)
_RE_DDL = re.compile(
    r"^\s*(CREATE|ALTER|DROP|TRUNCATE|RENAME|COMMENT)\b", re.IGNORECASE
)
_RE_DANGEROUS_IN_WRITE = re.compile(r"^\s*(DROP|TRUNCATE)\b", re.IGNORECASE)


def check_read_permission(config: DatabaseConfig, sql: str) -> None:
    """确认连接有读权限，且 SQL 是纯 SELECT 语句。"""
    if not config.permissions.allow_read:
        raise PermissionError("此连接没有读权限（allow_read=false）")
    if not _RE_SELECT.match(sql):
        raise SQLSafetyError(
            f"execute_query 只允许 SELECT 语句。收到: {sql[:60]!r}"
        )


def check_write_permission(config: DatabaseConfig, sql: str) -> None:
    """确认连接有写权限，且 SQL 是 DML（不含 DROP/TRUNCATE）。"""
    if not config.permissions.allow_write:
        raise PermissionError("此连接没有写权限（allow_write=false）")
    if _RE_DANGEROUS_IN_WRITE.match(sql):
        raise SQLSafetyError(
            "execute_write 不允许 DROP/TRUNCATE。如需执行，请使用 execute_ddl（需要 allow_ddl 权限）。"
        )
    if not _RE_WRITE.match(sql):
        raise SQLSafetyError(
            f"execute_write 只允许 INSERT/UPDATE/DELETE/REPLACE。收到: {sql[:60]!r}"
        )


def check_ddl_permission(config: DatabaseConfig, sql: str) -> None:
    """确认连接有 DDL 权限，且 SQL 是 DDL 语句。"""
    if not config.permissions.allow_ddl:
        raise PermissionError("此连接没有 DDL 权限（allow_ddl=false）")
    if not _RE_DDL.match(sql):
        raise SQLSafetyError(
            f"execute_ddl 只允许 CREATE/ALTER/DROP/TRUNCATE 等 DDL 语句。收到: {sql[:60]!r}"
        )


def validate_identifier(name: str) -> None:
    """校验表名/列名等 SQL 标识符，只允许字母、数字、下划线、连字符。"""
    if not re.match(r"^[a-zA-Z0-9_\-]+$", name):
        raise ValueError(f"无效的标识符: {name!r}（只允许字母、数字、_ 和 -）")
