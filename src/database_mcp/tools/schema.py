import json
from ..router import Router
from ..guard import PermissionError, validate_identifier


async def list_connections(router: Router) -> str:
    """列出所有已配置的数据库连接及其权限（不含密码）。"""
    connections = router.list_connections()
    result = json.dumps(connections, ensure_ascii=False, indent=2)
    result += "\n\n请将以上连接列表展示给用户，让用户选择要使用的连接后再执行查询。"
    return result


async def list_tables(router: Router, connection: str) -> str:
    """列出指定连接的数据库中所有表名。"""
    config = router.get_config(connection)
    if not config.permissions.allow_read:
        raise PermissionError(f"连接 '{connection}' 没有读权限（allow_read=false）")
    pool = router.get_pool(connection)
    tables = await pool.fetch_tables()
    return json.dumps(tables, ensure_ascii=False, indent=2)


async def describe_table(router: Router, connection: str, table: str) -> str:
    """返回指定表的列结构信息。"""
    config = router.get_config(connection)
    if not config.permissions.allow_read:
        raise PermissionError(f"连接 '{connection}' 没有读权限（allow_read=false）")
    validate_identifier(table)
    pool = router.get_pool(connection)
    columns = await pool.describe_table(table)
    return json.dumps(columns, default=str, ensure_ascii=False, indent=2)
