import pytest
import pandas as pd
import numpy as np
from etl.transform import EmsTransformer

@pytest.fixture
def transformer():
    return EmsTransformer()

def test_invalid_timestamp_sequence(transformer):
    # Data where arrival is before dispatch
    data = {
        '_id': ['REC_001'],
        'INCIDENT_DT': ['2026-04-01'],
        'INCIDENT_COUNTY': ['Shelby'],
        'UNIT_NOTIFIED_BY_DISPATCH_DT': ['2026-04-01 10:00:00'],
        'UNIT_ARRIVED_ON_SCENE_DT': ['2026-04-01 09:50:00'] # 10 mins before dispatch
    }
    df = pd.DataFrame(data)
    valid, rejected = transformer.clean_and_validate(df)
    
    assert len(rejected) == 1
    assert rejected.iloc[0]['ErrorCategory'] == "Invalid Timestamp Sequence"

def test_negative_duration_outlier(transformer):
    data = {
        '_id': ['REC_002'],
        'INCIDENT_DT': ['2026-04-01'],
        'INCIDENT_COUNTY': ['Shelby'],
        'PROVIDER_TO_SCENE_MINS': [-5], # Negative value
        'PROVIDER_TO_DESTINATION_MINS': [10]
    }
    df = pd.DataFrame(data)
    valid, rejected = transformer.clean_and_validate(df)
    
    assert len(rejected) == 1
    assert "Duration Outlier" in rejected.iloc[0]['ErrorCategory']

def test_missing_critical_id(transformer):
    data = {
        '_id': [np.nan], 
        'INCIDENT_DT': ['2026-04-01'],
        'INCIDENT_COUNTY': ['Shelby']
    }
    df = pd.DataFrame(data)
    valid, rejected = transformer.clean_and_validate(df)

    assert len(rejected) == 1
    assert "Missing Critical Info" in rejected.iloc[0]['ErrorCategory']