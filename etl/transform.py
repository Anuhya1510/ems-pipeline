import pandas as pd
import numpy as np
from .logger import get_logger

logger = get_logger("EMS_TRANSFORMER")

class EmsTransformer:
    def __init__(self):
        # Critical fields required for a record to even be considered
        self.critical_columns = ['_id', 'INCIDENT_DT', 'INCIDENT_COUNTY']
        
        # NEMSIS-specific "Null" strings to be treated as NaN
        self.nemsis_nulls = [
            'Not Applicable', 'Not Recorded', 'Not Reporting', 
            'Not Available', 'Anomalous', 'None'
        ]

    def clean_and_validate(self, df: pd.DataFrame):
        if df.empty:
            return df, df

        df = df.copy()
        df['is_valid'] = True
        df['QuarantineReason'] = ""
        df['ErrorCategory'] = "Valid"

        # 1. Pre-Processing: Standardize Data Types
        date_cols = [
            'UNIT_NOTIFIED_BY_DISPATCH_DT', 'UNIT_ARRIVED_ON_SCENE_DT',
            'UNIT_ARRIVED_TO_PATIENT_DT', 'UNIT_LEFT_SCENE_DT', 
            'PATIENT_ARRIVED_DESTINATION_DT', 'INCIDENT_DT'
        ]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

        duration_cols = ['PROVIDER_TO_SCENE_MINS', 'PROVIDER_TO_DESTINATION_MINS']
        for col in duration_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 2. Validation Rule: Critical Fields (Check for null's)
        for col in self.critical_columns:
            if col in df.columns:
                missing_crit = df[col].isna() & df['is_valid']
                df.loc[missing_crit, 'is_valid'] = False
                df.loc[missing_crit, 'ErrorCategory'] = "Missing Critical Info"
                df.loc[missing_crit, 'QuarantineReason'] += f"Missing {col}; "
            else:
                df['is_valid'] = False
                df['ErrorCategory'] = "Schema Mismatch"
                df['QuarantineReason'] += f"Column {col} missing from source; "

        # 3. Validation Rule: Timestamp Sequence
        if 'UNIT_ARRIVED_ON_SCENE_DT' in df.columns and 'UNIT_NOTIFIED_BY_DISPATCH_DT' in df.columns:
            seq_fail = (df['UNIT_ARRIVED_ON_SCENE_DT'] < df['UNIT_NOTIFIED_BY_DISPATCH_DT']) & df['is_valid']
            df.loc[seq_fail, 'is_valid'] = False
            df.loc[seq_fail, 'ErrorCategory'] = "Invalid Timestamp Sequence"
            df.loc[seq_fail, 'QuarantineReason'] += "Arrival before Dispatch; "

        # 4. Validation Rule: Duration Outliers & Negatives
        for col in duration_cols:
            if col in df.columns:
                math_fail = ((df[col] < 0) | (df[col] > 1440)) & df['is_valid']
                df.loc[math_fail, 'is_valid'] = False
                df.loc[math_fail, 'ErrorCategory'] = "Duration Outlier/Negative"
                df.loc[math_fail, 'QuarantineReason'] += f"{col} out of bounds; "

        # 5. Validation Rule: Duplicate Records
        if '_id' in df.columns:
            dupes = df.duplicated(subset=['_id'], keep='first') & df['is_valid']
            df.loc[dupes, 'is_valid'] = False
            df.loc[dupes, 'ErrorCategory'] = "Duplicate Record"
            df.loc[dupes, 'QuarantineReason'] += "Duplicate Incident ID; "

        # 6. Final Normalization: Injury Flag to Boolean
        if 'INJURY_FLG' in df.columns:
            df['INJURY_FLG'] = df['INJURY_FLG'].map({'Yes': True, 'No': False}).fillna(False)

        # Split into Valid and Rejected DataFrames
        valid_df = df[df['is_valid']].drop(columns=['is_valid', 'QuarantineReason', 'ErrorCategory'])
        rejected_df = df[~df['is_valid']]

        logger.info(f"Transformation Complete: {len(valid_df)} valid, {len(rejected_df)} quarantined.")
        
        return valid_df, rejected_df