import os
import re
import yaml
from pydantic import BaseModel, field_validator


class Permissions(BaseModel):
    allow_read: bool = True
    allow_write: bool = False
    allow_ddl: bool = False

    @field_validator("allow_read", "allow_write", "allow_ddl", mode="before")
    @classmethod
    def parse_bool_string(cls, v):
        """支持从环境变量传入的字符串布尔值，如 'true' / 'false'。"""
        if isinstance(v, str):
            if v.lower() in ("true", "1", "yes"):
                return True
            if v.lower() in ("false", "0", "no"):
                return False
            raise ValueError(f"Cannot parse '{v}' as boolean")
        return v


class DatabaseConfig(BaseModel):
    type: str
    host: str
    port: int
    database: str
    user: str
    password: str
    permissions: Permissions
    max_rows: int = 1000

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("mysql", "postgresql"):
            raise ValueError(
                f"Unsupported database type: {v!r}. Must be 'mysql' or 'postgresql'"
            )
        return v


class AppConfig(BaseModel):
    databases: dict[str, DatabaseConfig]


def _expand_env_vars(value: str) -> str:
    """将字符串中的 ${VAR_NAME} 替换为对应的环境变量值。"""
    def replace(match: re.Match) -> str:
        var_name = match.group(1)
        val = os.environ.get(var_name)
        if val is None:
            raise ValueError(
                f"Environment variable '{var_name}' is not set. "
                f"Add it to your .env file."
            )
        return val

    return re.sub(r"\$\{([^}]+)\}", replace, value)


def _expand_config_dict(data: dict) -> dict:
    """递归展开字典中所有字符串值的环境变量占位符。"""
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = _expand_env_vars(value)
        elif isinstance(value, dict):
            result[key] = _expand_config_dict(value)
        else:
            result[key] = value
    return result


def load_config(path: str = "databases.yaml") -> AppConfig:
    """从 YAML 文件加载并校验数据库配置。"""
    with open(path) as f:
        raw = yaml.safe_load(f)
    expanded = _expand_config_dict(raw)
    return AppConfig(**expanded)
