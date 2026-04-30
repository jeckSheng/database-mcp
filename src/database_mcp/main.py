import asyncio
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from .config import load_config
from .pool import DatabasePool
from .router import Router
from .tools import query as query_tools
from .tools import schema as schema_tools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("database-mcp")

app = Server("database-mcp")
_router: Router | None = None


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_connections",
            description="列出所有已配置的数据库连接及其权限信息。调用后必须将连接列表展示给用户，让用户选择要使用的连接，不要自动选择。",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="execute_query",
            description="在指定连接上执行 SELECT 查询，最多返回 1000 行",
            inputSchema={
                "type": "object",
                "properties": {
                    "connection": {
                        "type": "string",
                        "description": "数据库连接名称（来自 databases.yaml）",
                    },
                    "sql": {
                        "type": "string",
                        "description": "SELECT SQL 语句",
                    },
                },
                "required": ["connection", "sql"],
            },
        ),
        types.Tool(
            name="execute_write",
            description="在指定连接上执行 INSERT / UPDATE / DELETE 操作",
            inputSchema={
                "type": "object",
                "properties": {
                    "connection": {"type": "string", "description": "数据库连接名称"},
                    "sql": {
                        "type": "string",
                        "description": "INSERT / UPDATE / DELETE SQL 语句",
                    },
                },
                "required": ["connection", "sql"],
            },
        ),
        types.Tool(
            name="execute_ddl",
            description="在指定连接上执行 DDL 语句（CREATE / ALTER / DROP / TRUNCATE）",
            inputSchema={
                "type": "object",
                "properties": {
                    "connection": {"type": "string", "description": "数据库连接名称"},
                    "sql": {"type": "string", "description": "DDL SQL 语句"},
                },
                "required": ["connection", "sql"],
            },
        ),
        types.Tool(
            name="list_tables",
            description="列出指定数据库连接中的所有表名",
            inputSchema={
                "type": "object",
                "properties": {
                    "connection": {"type": "string", "description": "数据库连接名称"},
                },
                "required": ["connection"],
            },
        ),
        types.Tool(
            name="describe_table",
            description="查看指定表的列结构（字段名、类型、是否可空等）",
            inputSchema={
                "type": "object",
                "properties": {
                    "connection": {"type": "string", "description": "数据库连接名称"},
                    "table": {"type": "string", "description": "表名"},
                },
                "required": ["connection", "table"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    conn = arguments.get("connection", "-")
    sql_preview = ""
    if "sql" in arguments:
        sql = arguments["sql"].strip().replace("\n", " ")
        sql_preview = f" | sql: {sql[:80]}{'...' if len(sql) > 80 else ''}"

    logger.info(f"[{name}] conn={conn}{sql_preview}")

    try:
        if name == "list_connections":
            result = await schema_tools.list_connections(_router)
        elif name == "execute_query":
            result = await query_tools.execute_query(
                _router, arguments["connection"], arguments["sql"]
            )
        elif name == "execute_write":
            result = await query_tools.execute_write(
                _router, arguments["connection"], arguments["sql"]
            )
        elif name == "execute_ddl":
            result = await query_tools.execute_ddl(
                _router, arguments["connection"], arguments["sql"]
            )
        elif name == "list_tables":
            result = await schema_tools.list_tables(_router, arguments["connection"])
        elif name == "describe_table":
            result = await schema_tools.describe_table(
                _router, arguments["connection"], arguments["table"]
            )
        else:
            result = f"未知工具: {name}"

        logger.info(f"[{name}] OK | {len(result)} chars")
    except Exception as e:
        logger.warning(f"[{name}] ERR | {type(e).__name__}: {e}")
        result = f"错误 [{type(e).__name__}]: {e}"

    return [types.TextContent(type="text", text=result)]


async def main() -> None:
    global _router
    logger.info("正在加载数据库配置...")
    config = load_config()

    logger.info(f"初始化 {len(config.databases)} 个数据库连接池...")
    pools: dict[str, DatabasePool] = {}
    for name, db_cfg in config.databases.items():
        pool = DatabasePool(name, db_cfg)
        await pool.initialize()
        pools[name] = pool
        logger.info(f"  ✓ {name} ({db_cfg.type}:{db_cfg.host}/{db_cfg.database})")

    _router = Router(config, pools)
    logger.info("MCP Server 启动，等待连接...")

    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream, write_stream, app.create_initialization_options()
            )
    finally:
        logger.info("正在关闭连接池...")
        for pool in pools.values():
            await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
