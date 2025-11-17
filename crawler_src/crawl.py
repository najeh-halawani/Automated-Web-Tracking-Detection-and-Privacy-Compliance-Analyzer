'''
Author: Najeh Halawani
-----
Last Modified: Monday, 10th November 2025 12:13:12 pm
Modified By: Najeh Halawani
-----
'''

import argparse
import logging
import sys
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

from crawler_src.runs import run_accept, run_reject, run_block
from crawler_src.utils import setup_logging


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Web Privacy Crawler",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '-m',
        type=str,
        choices=['accept', 'reject', 'block'],
        required=True,
        help="Crawl mode: accept, reject, or block"
    )
    
    parser.add_argument(
        '-l',
        type=str,
        help="Path to the site list CSV (default: ./site_list.csv)"
    )
    
    parser.add_argument(
        '-w',
        '--workers',
        type=int,
        default=5,
        help="Number of parallel workers (default: 5)"
    )
    
    return parser.parse_args()


def main():
    logger = setup_logging()

    
    args = parse_arguments()
    
    logger.info(f"Crawl mode: {args.m}")
    logger.info(f"Site list: {args.l or './site_list.csv'}")
    
    site_list_file = args.l if args.l else "./site_list.csv"
    
    site_list_path = Path(site_list_file)
    if not site_list_path.exists():
        logger.error(f"Site list file not found: {site_list_file}")
        sys.exit(1)
    
    try:
        df = pd.read_csv(site_list_path)
        logger.info(f"Loaded {len(df)} sites from list")
    except Exception as e:
        logger.error(f"Error reading site list: {e}")
        sys.exit(1)
    
    if 'domain' not in df.columns:
        logger.error("Site list must have 'domain' column")
        sys.exit(1)
    
    domains = df['domain'].tolist()
    
    crawl_functions = {
        "accept": run_accept,
        "reject": run_reject,
        "block": run_block
    }
    
    crawl_func = crawl_functions[args.m]
    
    total_sites = len(domains)
    successful = 0
    failed = 0
    
    # Thread-safe counter lock
    counter_lock = threading.Lock()
    
    def crawl_worker(domain: str, index: int):
        """Worker function to crawl a single domain."""
        nonlocal successful, failed
        thread_name = threading.current_thread().name
        
        logger.info("="*80)
        logger.info(f"[{index}/{total_sites}] Crawling: {domain} (Thread: {thread_name})")
        logger.info("="*80)
        
        try:
            crawl_func(domain)
            with counter_lock:
                successful += 1
                current_success = successful
                current_failed = failed
            logger.info(f"Successfully crawled: {domain} (Thread: {thread_name})")
            logger.info(f"Progress: {current_success} successful, {current_failed} failed out of {total_sites} total")
            return True, domain, None
        except Exception as e:
            with counter_lock:
                failed += 1
                current_success = successful
                current_failed = failed
            logger.error(f"Failed to crawl {domain}: {e}", exc_info=True)
            logger.info(f"Progress: {current_success} successful, {current_failed} failed out of {total_sites} total")
            return False, domain, str(e)
    
    # Use ThreadPoolExecutor for parallel execution
    logger.info(f"Starting parallel crawl with {args.workers} workers")
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all crawl tasks
        future_to_domain = {
            executor.submit(crawl_worker, domain, idx): domain 
            for idx, domain in enumerate(domains, 1)
        }
        
        # Process completed tasks as they finish
        for future in as_completed(future_to_domain):
            domain = future_to_domain[future]
            try:
                success, crawled_domain, error = future.result()
            except Exception as e:
                with counter_lock:
                    failed += 1
                logger.error(f"Unexpected error processing {domain}: {e}", exc_info=True)
    
    logger.info("="*80)
    logger.info(f"Crawl completed: {successful} successful, {failed} failed out of {total_sites} total")
    logger.info("="*80)

if __name__ == "__main__":
    main()