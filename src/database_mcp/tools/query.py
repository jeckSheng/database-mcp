import json
from ..router import Router
from ..guard import check_read_permission, check_write_permission, check_ddl_permission


async def execute_query(router: Router, connection: str, sql: str) -> str:
    """执行 SELECT 查询，以 JSON 字符串返回结果集。"""
    config = router.get_config(connection)
    check_read_permission(config, sql)
    pool = router.get_pool(connection)
    rows = await pool.fetch_all(sql)
    return json.dumps(rows, default=str, ensure_ascii=False, indent=2)


async def execute_write(router: Router, connection: str, sql: str) -> str:
    """执行 INSERT/UPDATE/DELETE，返回影响行数描述。"""
    config = router.get_config(connection)
    check_write_permission(config, sql)
    pool = router.get_pool(connection)
    return await pool.execute(sql)


async def execute_ddl(router: Router, connection: str, sql: str) -> str:
    """执行 DDL 语句，返回执行状态描述。"""
    config = router.get_config(connection)
    check_ddl_permission(config, sql)
    pool = router.get_pool(connection)
    return await pool.execute(sql)
