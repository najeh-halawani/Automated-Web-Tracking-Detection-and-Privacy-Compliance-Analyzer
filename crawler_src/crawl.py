"""
Author: Najeh Halawani
-----
Last Modified: Monday, 10th November 2025 12:13:12 pm
Modified By: Najeh Halawani
-----
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

from crawler_src.runs import run_accept, run_reject
from crawler_src.utils import setup_logging
from crawler_src.crawlers.crawler_block import run_block


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Web Privacy Crawler",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-m",
        type=str,
        choices=["accept", "reject", "block"],
        required=True,
        help="Crawl mode: accept, reject, or block",
    )

    parser.add_argument(
        "-l", type=str, help="Path to the site list CSV (default: ./site_list.csv)"
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

    if "domain" not in df.columns:
        logger.error("Site list must have 'domain' column")
        sys.exit(1)

    domains = df["domain"].tolist()

    crawl_functions = {"accept": run_accept, "reject": run_reject, "block": run_block}

    crawl_func = crawl_functions[args.m]

    total_sites = len(domains)
    successful = 0
    failed = 0

    for idx, domain in enumerate(domains, 1):
        logger.info("=" * 80)
        logger.info(f"[{idx}/{total_sites}] Crawling: {domain}")
        logger.info("=" * 80)

        try:
            crawl_func(domain)
            successful += 1
            logger.info(f"Successfully crawled: {domain}")
        except Exception as e:
            failed += 1
            logger.error(f"Failed to crawl {domain}: {e}", exc_info=True)

        logger.info(f"Progress: {successful} successful, {failed} failed")


if __name__ == "__main__":
    main()
