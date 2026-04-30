import pytest
from database_mcp.config import load_config, AppConfig, DatabaseConfig, Permissions


def test_load_config_basic(tmp_path):
    """最基础的 YAML 加载：MySQL 连接，只读权限"""
    yaml_content = """
databases:
  test_mysql:
    type: mysql
    host: localhost
    port: 3306
    database: testdb
    user: root
    password: secret
    permissions:
      allow_read: true
      allow_write: false
      allow_ddl: false
"""
    config_file = tmp_path / "databases.yaml"
    config_file.write_text(yaml_content)
    config = load_config(str(config_file))
    assert "test_mysql" in config.databases
    db = config.databases["test_mysql"]
    assert db.type == "mysql"
    assert db.host == "localhost"
    assert db.permissions.allow_read is True
    assert db.permissions.allow_write is False


def test_load_config_env_var_expansion(tmp_path, monkeypatch):
    """${ENV_VAR} 占位符应被替换为环境变量值"""
    monkeypatch.setenv("TEST_PASSWORD", "my_secret_pw")
    yaml_content = """
databases:
  test_pg:
    type: postgresql
    host: localhost
    port: 5432
    database: testdb
    user: testuser
    password: "${TEST_PASSWORD}"
    permissions:
      allow_read: true
      allow_write: true
      allow_ddl: false
"""
    config_file = tmp_path / "databases.yaml"
    config_file.write_text(yaml_content)
    config = load_config(str(config_file))
    assert config.databases["test_pg"].password == "my_secret_pw"


def test_load_config_missing_env_var(tmp_path):
    """引用不存在的环境变量应抛出 ValueError"""
    yaml_content = """
databases:
  test_pg:
    type: postgresql
    host: localhost
    port: 5432
    database: testdb
    user: testuser
    password: "${NONEXISTENT_VAR_XYZ}"
    permissions:
      allow_read: true
      allow_write: false
      allow_ddl: false
"""
    config_file = tmp_path / "databases.yaml"
    config_file.write_text(yaml_content)
    with pytest.raises(ValueError, match="NONEXISTENT_VAR_XYZ"):
        load_config(str(config_file))


def test_load_config_invalid_db_type(tmp_path):
    """不支持的数据库类型应抛出 ValidationError"""
    yaml_content = """
databases:
  test_mongo:
    type: mongodb
    host: localhost
    port: 27017
    database: testdb
    user: root
    password: secret
    permissions:
      allow_read: true
      allow_write: false
      allow_ddl: false
"""
    config_file = tmp_path / "databases.yaml"
    config_file.write_text(yaml_content)
    with pytest.raises(Exception):
        load_config(str(config_file))


def test_permissions_defaults(tmp_path):
    """allow_write/allow_ddl 默认为 False，max_rows 默认 1000"""
    yaml_content = """
databases:
  test_db:
    type: mysql
    host: localhost
    port: 3306
    database: testdb
    user: root
    password: secret
    permissions:
      allow_read: true
"""
    config_file = tmp_path / "databases.yaml"
    config_file.write_text(yaml_content)
    config = load_config(str(config_file))
    db = config.databases["test_db"]
    assert db.permissions.allow_write is False
    assert db.permissions.allow_ddl is False
    assert db.max_rows == 1000


def test_load_multiple_databases(tmp_path):
    """能同时加载多个数据库连接"""
    yaml_content = """
databases:
  db_a:
    type: mysql
    host: host-a
    port: 3306
    database: dba
    user: u
    password: p
    permissions:
      allow_read: true
  db_b:
    type: postgresql
    host: host-b
    port: 5432
    database: dbb
    user: u
    password: p
    permissions:
      allow_read: true
      allow_write: true
"""
    config_file = tmp_path / "databases.yaml"
    config_file.write_text(yaml_content)
    config = load_config(str(config_file))
    assert len(config.databases) == 2
    assert config.databases["db_b"].type == "postgresql"
    assert config.databases["db_b"].permissions.allow_write is True
