import logging
import sys
import os

def get_logger(name="EMS_PIPELINE"):
    logger = logging.getLogger(name)
    
    # Prevent duplicate handlers if get_logger is called multiple times
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Formatting for log aggregators
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
        )

        # Stream Handler
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        logger.addHandler(sh)

        if not os.path.exists('logs'):
            os.makedirs('logs')
        fh = logging.FileHandler('logs/pipeline.log')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
    return logger