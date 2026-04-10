import pandas as pd
from sqlalchemy import text
from .logger import get_logger
from sqlalchemy.types import NVARCHAR
import pyodbc

logger = get_logger("EMS_LOADER")

class EmsLoader:
    def __init__(self, engine):
        self.engine = engine

    def load_staging(self, df: pd.DataFrame, table_name="STG_EMS_INCIDENTS", mode='replace'):
        logger.info(f"Loading to Staging ({mode}): {table_name}")
        df.to_sql(table_name, self.engine, if_exists=mode, index=False)

    def load_quarantine(self, df: pd.DataFrame):
        if df.empty:
            return

        logger.warning(f"Logging {len(df)} rejected records to ERR_Quarantine.")
        
        raw_conn = self.engine.raw_connection()
        try:
            cursor = raw_conn.cursor()

            # Truncate Table
            #cursor.execute("TRUNCATE TABLE ERR_Quarantine")
            
            sql = """
                INSERT INTO ERR_Quarantine (RecordID, ErrorReason, ErrorCategory, RawData) 
                VALUES (?, ?, ?, ?)
            """
            
            for _, row in df.iterrows():
                cursor.execute(sql, (
                    str(row['_id']),
                    str(row['QuarantineReason']),
                    str(row['ErrorCategory']),
                    row.to_json()
                ))

            raw_conn.commit()
            logger.info("Successfully quarantined records.")
            
        except Exception as e:
            logger.error(f"Failed to load quarantine: {str(e)}")
            raw_conn.rollback()
            raise
        finally:
            raw_conn.close()

    def populate_dimensions(self):
        logger.info("Syncing Dimensions via MERGE...")
        with self.engine.begin() as conn:
            # Dim_Location Merge
            conn.execute(text("""
                MERGE INTO Dim_Location AS T
                USING (SELECT DISTINCT INCIDENT_COUNTY, DESTINATION_TYPE 
                       FROM STG_EMS_INCIDENTS 
                       WHERE INCIDENT_COUNTY IS NOT NULL) AS S
                ON ISNULL(T.CountyName,'') = ISNULL(S.INCIDENT_COUNTY,'') 
                AND ISNULL(T.DestinationType,'') = ISNULL(S.DESTINATION_TYPE,'')
                WHEN NOT MATCHED THEN
                    INSERT (CountyName, DestinationType) VALUES (S.INCIDENT_COUNTY, S.DESTINATION_TYPE);
            """))
            
            # Dim_Provider Merge
            conn.execute(text("""
                MERGE INTO Dim_Provider AS T
                USING (SELECT DISTINCT PROVIDER_TYPE_STRUCTURE, PROVIDER_TYPE_SERVICE, PROVIDER_TYPE_SERVICE_LEVEL 
                       FROM STG_EMS_INCIDENTS) AS S
                ON ISNULL(T.Structure,'') = ISNULL(S.PROVIDER_TYPE_STRUCTURE,'') 
                AND ISNULL(T.ServiceType,'') = ISNULL(S.PROVIDER_TYPE_SERVICE,'') 
                AND ISNULL(T.ServiceLevel,'') = ISNULL(S.PROVIDER_TYPE_SERVICE_LEVEL,'')
                WHEN NOT MATCHED THEN
                    INSERT (Structure, ServiceType, ServiceLevel) 
                    VALUES (S.PROVIDER_TYPE_STRUCTURE, S.PROVIDER_TYPE_SERVICE, S.PROVIDER_TYPE_SERVICE_LEVEL);
            """))

    def execute_upsert_fact(self):
        logger.info("Merging Fact Data...")
        query = """
        WITH SourceCTE AS (
            SELECT s._id, s.INCIDENT_DT, s.PROVIDER_TO_SCENE_MINS, s.INJURY_FLG,
                   l.LocationKey, p.ProviderKey,
                   ROW_NUMBER() OVER(PARTITION BY s._id ORDER BY s.INCIDENT_DT) as rnk
            FROM STG_EMS_INCIDENTS s
            LEFT JOIN Dim_Location l ON ISNULL(s.INCIDENT_COUNTY,'') = ISNULL(l.CountyName,'') 
                AND ISNULL(s.DESTINATION_TYPE,'') = ISNULL(l.DestinationType,'')
            LEFT JOIN Dim_Provider p ON ISNULL(s.PROVIDER_TYPE_STRUCTURE,'') = ISNULL(p.Structure,'') 
                AND ISNULL(s.PROVIDER_TYPE_SERVICE,'') = ISNULL(p.ServiceType,'')
                AND ISNULL(s.PROVIDER_TYPE_SERVICE_LEVEL,'') = ISNULL(p.ServiceLevel, '')
        )
        MERGE INTO Fact_EMS_Incidents AS T
        USING (SELECT * FROM SourceCTE WHERE rnk = 1) AS S ON T.IncidentID = S._id
        WHEN MATCHED THEN
            UPDATE SET T.IncidentTimestamp = S.INCIDENT_DT, T.ToSceneMins = S.PROVIDER_TO_SCENE_MINS, 
                       T.LocationKey = S.LocationKey, T.ProviderKey = S.ProviderKey
        WHEN NOT MATCHED THEN
            INSERT (IncidentID, IncidentTimestamp, ToSceneMins, IsInjury, LocationKey, ProviderKey)
            VALUES (S._id, S.INCIDENT_DT, S.PROVIDER_TO_SCENE_MINS, S.INJURY_FLG, S.LocationKey, S.ProviderKey);
        """
        with self.engine.begin() as conn:
            conn.execute(text(query))