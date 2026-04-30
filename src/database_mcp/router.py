from .config import AppConfig, DatabaseConfig
from .pool import DatabasePool


class Router:
    """按 connection_name 将请求路由到对应的连接池和配置。"""

    def __init__(self, config: AppConfig, pools: dict[str, DatabasePool]) -> None:
        self._config = config
        self._pools = pools

    def get_pool(self, connection_name: str) -> DatabasePool:
        if connection_name not in self._pools:
            available = list(self._pools.keys())
            raise KeyError(
                f"未知的连接名 '{connection_name}'。可用连接: {available}"
            )
        return self._pools[connection_name]

    def get_config(self, connection_name: str) -> DatabaseConfig:
        if connection_name not in self._config.databases:
            available = list(self._config.databases.keys())
            raise KeyError(
                f"未知的连接名 '{connection_name}'。可用连接: {available}"
            )
        return self._config.databases[connection_name]

    def list_connections(self) -> list[dict]:
        """返回所有连接的基本信息，不包含密码。"""
        result = []
        for name, db_cfg in self._config.databases.items():
            result.append(
                {
                    "name": name,
                    "type": db_cfg.type,
                    "host": db_cfg.host,
                    "database": db_cfg.database,
                    "permissions": {
                        "allow_read": db_cfg.permissions.allow_read,
                        "allow_write": db_cfg.permissions.allow_write,
                        "allow_ddl": db_cfg.permissions.allow_ddl,
                    },
                }
            )
        return result
