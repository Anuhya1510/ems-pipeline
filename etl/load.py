import pandas as pd
from sqlalchemy import text
from .logger import get_logger

logger = get_logger("EMS_LOADER")

class EmsLoader:
    def __init__(self, engine):
        self.engine = engine

    def load_staging(self, df: pd.DataFrame, table_name="STG_EMS_INCIDENTS"):
        logger.info(f"Refreshing Staging: {table_name}")
        df.to_sql(table_name, self.engine, if_exists='replace', index=False)

    def load_quarantine(self, df: pd.DataFrame):
        if df.empty:
            return

        logger.warning(f"Logging {len(df)} rejected records to ERR_Quarantine.")
        
        error_records = pd.DataFrame({
            'RecordID': df['_id'].astype(str),
            'ErrorReason': df['QuarantineReason'],
            'RawData': df.to_json(orient='records', lines=True).splitlines()
        })

        error_records.to_sql('ERR_Quarantine', self.engine, if_exists='append', index=False)

    def populate_dimensions(self):
        logger.info("Syncing Dimensions...")
        with self.engine.begin() as conn:
            # Dim_Location
            conn.execute(text("""
                INSERT INTO Dim_Location (CountyName, DestinationType)
                SELECT DISTINCT INCIDENT_COUNTY, DESTINATION_TYPE
                FROM STG_EMS_INCIDENTS s
                WHERE s.INCIDENT_COUNTY IS NOT NULL 
                AND NOT EXISTS (
                    SELECT 1 FROM Dim_Location d 
                    WHERE ISNULL(d.CountyName,'') = ISNULL(s.INCIDENT_COUNTY,'') 
                    AND ISNULL(d.DestinationType,'') = ISNULL(s.DESTINATION_TYPE,'')
                )
            """))
            # Dim_Provider
            conn.execute(text("""
                INSERT INTO Dim_Provider (Structure, ServiceType, ServiceLevel)
                SELECT DISTINCT PROVIDER_TYPE_STRUCTURE, PROVIDER_TYPE_SERVICE, PROVIDER_TYPE_SERVICE_LEVEL
                FROM STG_EMS_INCIDENTS s
                WHERE NOT EXISTS (
                    SELECT 1 FROM Dim_Provider d 
                    WHERE ISNULL(d.Structure,'') = ISNULL(s.PROVIDER_TYPE_STRUCTURE,'') 
                    AND ISNULL(d.ServiceType,'') = ISNULL(s.PROVIDER_TYPE_SERVICE,'')
                    AND ISNULL(d.ServiceLevel,'') = ISNULL(s.PROVIDER_TYPE_SERVICE_LEVEL,'')
                )
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
            UPDATE SET 
                T.IncidentTimestamp = S.INCIDENT_DT,
                T.ToSceneMins = S.PROVIDER_TO_SCENE_MINS, 
                T.LocationKey = S.LocationKey,
                T.ProviderKey = S.ProviderKey
        WHEN NOT MATCHED THEN
            INSERT (IncidentID, IncidentTimestamp, ToSceneMins, IsInjury, LocationKey, ProviderKey)
            VALUES (S._id, S.INCIDENT_DT, S.PROVIDER_TO_SCENE_MINS, S.INJURY_FLG, S.LocationKey, S.ProviderKey);
        """
        with self.engine.begin() as conn:
            conn.execute(text(query))