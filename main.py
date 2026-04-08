import os
import pandas as pd
from etl import (
    get_logger, get_engine, ConfigManager, 
    EmsExtractor, EmsTransformer, EmsLoader
)
from etl.db import get_last_run_timestamp, update_last_run_timestamp

logger = get_logger("EMS_ORCHESTRATOR")

def run_pipeline():
    cfg = ConfigManager.get()
    input_file = cfg['source_settings']['input_file']
    landing_path = os.path.join(cfg['paths']['landing_zone'], input_file)
    
    try:
        engine = get_engine()
        
        # 1. Extraction
        logger.info(f"Extracting: {landing_path}")
        last_run_ts = get_last_run_timestamp(engine)
        chunk_size = 5000
        extractor = EmsExtractor(landing_path)
        raw_chunks = extractor.to_dataframe(chunksize=chunk_size)
        valid_dfs = []
        rejected_dfs = []
        total_count = 0

        # 2. Transformation 
        transformer = EmsTransformer()

        for chunk in raw_chunks:
            total_count += len(chunk)
            # Incremental filter
            if 'INCIDENT_DT' in chunk.columns:
                chunk['INCIDENT_DT'] = pd.to_datetime(chunk['INCIDENT_DT'], errors='coerce')
                chunk = chunk[chunk['INCIDENT_DT'] > last_run_ts]

            valid_df, rejected_df = transformer.clean_and_validate(chunk)

            valid_dfs.append(valid_df)
            rejected_dfs.append(rejected_df)
        valid_df = pd.concat(valid_dfs, ignore_index=True)
        rejected_df = pd.concat(rejected_dfs, ignore_index=True)

        # 3. Load Logic
        loader = EmsLoader(engine)
        
        # A: Load valid data to Staging
        loader.load_staging(valid_df)
        
        # B: Populate Dimensions
        loader.populate_dimensions()
        
        # C: Merge into Fact
        loader.execute_upsert_fact()

        # D: Handle Bad Data
        if not rejected_df.empty:
            loader.load_quarantine(rejected_df)
        else:
            logger.info("No malformed records found to quarantine.")

        # Data Quality Summary
        success_rate = (len(valid_df) / total_count) * 100
        print("-" * 30)
        print("Pipeline Quality Audit")
        print("-" * 30)
        print(f"Total Records:  {total_count}")
        print(f"Valid Records:  {len(valid_df)} ({success_rate:.2f}%)")
        print(f"Rejected:       {len(rejected_df)}")
        if not rejected_df.empty:
            print("\nRejection Breakdown:")
            print(rejected_df['ErrorCategory'].value_counts())
        print("-" * 30)

        logger.info("Pipeline Execution Complete.")

        if not valid_df.empty:
            max_ts = valid_df['INCIDENT_DT'].max()
            update_last_run_timestamp(engine, max_ts)

    except Exception as e:
        logger.error(f"Critical Failure: {str(e)}", exc_info=True)

if __name__ == "__main__":
    run_pipeline()