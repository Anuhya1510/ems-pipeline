import os
import pandas as pd
from collections import Counter
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
        
        # Tracking variables for memory efficiency
        total_count = 0
        total_valid_len = 0
        total_rejected_len = 0
        rejection_counts = Counter()
        first_chunk = True

        # 2. Transformation 
        transformer = EmsTransformer()
        loader = EmsLoader(engine)

        for chunk in raw_chunks:
            total_count += len(chunk)
            # Incremental filter
            if 'INCIDENT_DT' in chunk.columns:
                chunk['INCIDENT_DT'] = pd.to_datetime(chunk['INCIDENT_DT'], errors='coerce')
                chunk = chunk[chunk['INCIDENT_DT'] > last_run_ts]

            valid_chunk, rejected_chunk = transformer.clean_and_validate(chunk)
            
            # Update running totals
            total_valid_len += len(valid_chunk)
            total_rejected_len += len(rejected_chunk)
            if not rejected_chunk.empty:
                rejection_counts.update(rejected_chunk['ErrorCategory'].tolist())

            # 3. Load Logic (Chunk-based streaming)
            
            # A: Load valid data to Staging
            if not valid_chunk.empty:
                # Use 'replace' for first chunk to clear table, 'append' thereafter
                load_mode = 'replace' if first_chunk else 'append'
                loader.load_staging(valid_chunk, mode=load_mode)
                first_chunk = False
            
            # D: Handle Bad Data (Streaming to Quarantine)
            if not rejected_chunk.empty:
                loader.load_quarantine(rejected_chunk)

        # After all chunks are processed, finalize the Warehouse
        if total_valid_len > 0:
            # B: Populate Dimensions
            loader.populate_dimensions()
            
            # C: Merge into Fact
            loader.execute_upsert_fact()
        else:
            logger.info("No new records found to process.")

        # Data Quality Summary
        success_rate = (total_valid_len / total_count) * 100 if total_count > 0 else 0
        print("-" * 30)
        print("Pipeline Quality Audit")
        print("-" * 30)
        print(f"Total Records:  {total_count}")
        print(f"Valid Records:  {total_valid_len} ({success_rate:.2f}%)")
        print(f"Rejected:       {total_rejected_len}")
        if total_rejected_len > 0:
            print("\nRejection Breakdown:")
            for category, count in rejection_counts.items():
                print(f"{category:<28} {count}")
        print("-" * 30)

        logger.info("Pipeline Execution Complete.")

        # Update watermark if data was processed
        if total_valid_len > 0:
            update_last_run_timestamp(engine, pd.to_datetime('now'))

    except Exception as e:
        logger.error(f"Critical Failure: {str(e)}", exc_info=True)

if __name__ == "__main__":
    run_pipeline()