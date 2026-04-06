import pandas as pd
import numpy as np
from .logger import get_logger

logger = get_logger("EMS_TRANSFORMER")

class EmsTransformer:
    def __init__(self):
        # Critical fields
        self.critical_columns = ['_id', 'INCIDENT_DT', 'INCIDENT_COUNTY']
        
        # NEMSIS-specific "Null" strings
        self.nemsis_nulls = [
            'Not Applicable', 'Not Recorded', 'Not Reporting', 
            'Not Available', 'Anomalous', 'None'
        ]

    def clean_and_validate(self, df: pd.DataFrame):
        if df.empty:
            return df, df

        # Internal tracking columns
        df = df.copy()
        df['is_valid'] = True
        df['QuarantineReason'] = ""
        df['ErrorCategory'] = "Valid"

        # PRE-PROCESSING: Standardize Data Types
        # Coerce dates
        date_cols = [
            'UNIT_NOTIFIED_BY_DISPATCH_DT', 'UNIT_ARRIVED_ON_SCENE_DT',
            'UNIT_ARRIVED_TO_PATIENT_DT', 'UNIT_LEFT_SCENE_DT', 
            'PATIENT_ARRIVED_DESTINATION_DT', 'INCIDENT_DT'
        ]
        for col in date_cols:
            df[col] = pd.to_datetime(df[col], errors='coerce')

        # Clean NEMSIS Nulls in text columns
        df = df.replace(self.nemsis_nulls, np.nan)

        # RULE 1: Missing Critical Fields
        missing_crit = df[self.critical_columns].isnull().any(axis=1)
        df.loc[missing_crit, 'is_valid'] = False
        df.loc[missing_crit, 'ErrorCategory'] = "Missing Critical Fields"
        df.loc[missing_crit, 'QuarantineReason'] += "Missing ID, Date, or County; "

        # RULE 2: Invalid Timestamp Sequence
        # Logic: Arrival must be >= Dispatch
        seq_fail = (df['UNIT_ARRIVED_ON_SCENE_DT'] < df['UNIT_NOTIFIED_BY_DISPATCH_DT'])
        
        # Ensure we only flag rows that actually have both dates
        valid_seq_fail = seq_fail & df['is_valid'] 
        df.loc[valid_seq_fail, 'is_valid'] = False
        df.loc[valid_seq_fail, 'ErrorCategory'] = "Invalid Timestamp Sequence"
        df.loc[valid_seq_fail, 'QuarantineReason'] += "Arrived Scene before Dispatch; "

        # RULE 3: Negative Duration Values
        duration_cols = ['PROVIDER_TO_SCENE_MINS', 'PROVIDER_TO_DESTINATION_MINS']
        for col in duration_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        neg_duration = (df['PROVIDER_TO_SCENE_MINS'] < 0) | (df['PROVIDER_TO_DESTINATION_MINS'] < 0)
        extreme_outlier = (df['PROVIDER_TO_SCENE_MINS'] > 1440) # > 24 hours
        
        math_fail = (neg_duration | extreme_outlier) & df['is_valid']
        df.loc[math_fail, 'is_valid'] = False
        df.loc[math_fail, 'ErrorCategory'] = "Duration Outlier/Negative"
        df.loc[math_fail, 'QuarantineReason'] += "Duration is negative or exceeds 24h; "

        # RULE 4: Duplicate Records
        dupes = df.duplicated(subset=['_id'], keep='first') & df['is_valid']
        df.loc[dupes, 'is_valid'] = False
        df.loc[dupes, 'ErrorCategory'] = "Duplicate Record"
        df.loc[dupes, 'QuarantineReason'] += "Duplicate Incident ID; "

        # FINAL NORMALIZATION 
        # Convert Injury Flag to Boolean
        if 'INJURY_FLG' in df.columns:
            df['INJURY_FLG'] = df['INJURY_FLG'].map({'Yes': 1, 'No': 0, 1: 1, 0: 0}).fillna(0).astype(int)

        # Split the results
        valid_df = df[df['is_valid'] == True].drop(columns=['is_valid', 'QuarantineReason', 'ErrorCategory'])
        rejected_df = df[df['is_valid'] == False]

        logger.info(f"Transformation complete. Valid: {len(valid_df)}, Rejected: {len(rejected_df)}")
        return valid_df, rejected_df