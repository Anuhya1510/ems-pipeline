import yaml
import pathlib
import os
import urllib
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

base_path = pathlib.Path(__file__).parent.parent
load_dotenv(dotenv_path=base_path / ".env")

class ConfigManager:
    _config = None

    @classmethod
    def get(cls):
        if cls._config is None:
            config_path = base_path / "config" / "config.yaml"
            
            if not config_path.exists():
                raise FileNotFoundError(f"Configuration missing at {config_path}")
                
            with open(config_path, "r") as f:
                cls._config = yaml.safe_load(f)

            env_server = os.getenv("DB_SERVER")
            if env_server:
                cls._config['database']['server'] = env_server
            else:
                print("Warning: DB_SERVER not found in .env, using config.yaml default.")

        return cls._config

def get_engine():
    cfg = ConfigManager.get()['database']
    
    params = urllib.parse.quote_plus(
        f"DRIVER={cfg['driver']};"
        f"SERVER={cfg['server']};"
        f"DATABASE={cfg['database']};"
        f"Trusted_Connection={cfg['trusted_connection']};"
    )
    
    conn_str = f"mssql+pyodbc:///?odbc_connect={params}"
    
    return create_engine(conn_str, fast_executemany=True)


def get_last_run_timestamp(engine):
    query = """
        SELECT LastRunTimestamp 
        FROM ETL_Metadata 
        WHERE PipelineName = 'EMS_PIPELINE'
    """
    with engine.begin() as conn:
        result = conn.execute(text(query)).fetchone()
        return result[0]

def update_last_run_timestamp(engine, new_timestamp):
    query = """
        UPDATE ETL_Metadata
        SET LastRunTimestamp = :ts
        WHERE PipelineName = 'EMS_PIPELINE'
    """
    with engine.begin() as conn:
        conn.execute(text(query), {"ts": new_timestamp})