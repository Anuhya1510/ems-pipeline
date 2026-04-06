import os
from etl import (
    get_logger, get_engine, ConfigManager, 
    EmsExtractor, EmsTransformer, EmsLoader
)

logger = get_logger("EMS_ORCHESTRATOR")

def run_pipeline():
    cfg = ConfigManager.get()
    input_file = cfg['source_settings']['input_file']
    landing_path = os.path.join(cfg['paths']['landing_zone'], input_file)
    
    try:
        engine = get_engine()
        
        # 1. Extraction
        logger.info(f"Extracting: {landing_path}")
        raw_df = EmsExtractor(landing_path).to_dataframe()
        total_count = len(raw_df)

        # 2. Transformation 
        transformer = EmsTransformer()
        valid_df, rejected_df = transformer.clean_and_validate(raw_df)

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

    except Exception as e:
        logger.error(f"Critical Failure: {str(e)}", exc_info=True)

if __name__ == "__main__":
    run_pipeline()