'''
Author: Najeh Halawani
-----
Last Modified: Tuesday, 28th October 2025 8:14:49 pm
Modified By: Najeh Halawani
-----
'''
import warnings
import logging
import os
from datetime import datetime

def initialize_logging():
    warnings.filterwarnings("ignore")
    log_filename = f"{datetime.now():%Y-%m-%d_%H-%M-%S}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )