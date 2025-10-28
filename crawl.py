'''
Author: Najeh Halawani
-----
Last Modified: Tuesday, 28th October 2025 8:22:23 pm
Modified By: Najeh Halawani
-----
'''

import argparse
import logging
from runs import run_accept, run_reject, run_block
from utils import initialize_logging

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Run accept/reject/block actions.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '-m', type=str, choices=['accept', 'reject', 'block'], required=True,
        help="Mode to run the script in."
    )
    parser.add_argument(
        '-l', type=str, help="Path to the site list CSV (default: ./site_list.csv)"
    )
    
    return parser.parse_args()

def main():
    initialize_logging()
    args = parse_arguments()
    
    site_list = args.l or "./site_list.csv"
    if not args.l:
        logging.info("-l not specified. Using default: %s", site_list)
        
    if args.m == "accept":
        run_accept()
    elif args.m == "reject":
        run_reject()
    elif args.m == "block":
        run_block()
    else:
        raise Exception("Wrong method choice")

if __name__ == "__main__":
    main()
