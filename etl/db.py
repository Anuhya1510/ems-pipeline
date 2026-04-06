import yaml
import pathlib
import os
from sqlalchemy import create_engine

class ConfigManager:
    _config = None

    @classmethod
    def get(cls):
        if cls._config is None:
            base_path = pathlib.Path(__file__).parent.parent
            config_path = base_path / "config" / "config.yaml"
            
            if not config_path.exists():
                raise FileNotFoundError(f"Configuration missing at {config_path}")
                
            with open(config_path, "r") as f:
                cls._config = yaml.safe_load(f)
        return cls._config

def get_engine():
    cfg = ConfigManager.get()['database']
    conn_str = (
        f"mssql+pyodbc://{cfg['server']}/{cfg['database']}?"
        f"driver={cfg['driver'].replace(' ', '+')}&"
        f"trusted_connection={cfg['trusted_connection']}"
    )
    return create_engine(conn_str, fast_executemany=True)