'''
Author: Najeh Halawani
-----
Last Modified: Monday, 10th November 2025 12:18:34 pm
Modified By: Najeh Halawani
-----
'''
import warnings
import logging
import os
from datetime import datetime
from pathlib import Path
import json
import random
import time
from playwright.sync_api import Page
import sys

WORD_FILE = Path(__file__).parent / "words.json"

with open(WORD_FILE, "r", encoding="utf-8") as f:
    word_data = json.load(f)

accept_words = word_data["accept_words"]
words = word_data["words"]


def setup_logging():
    parent_dir = Path(__file__).parent.parent
    folders = ['crawl_data_block ', 'crawl_data_accept', 'crawl_data_reject', 'analysis', 'crawler_src' ]
    for folder in folders:
        folder_path = parent_dir / folder
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            logging.info(f"Created folder: {folder_path}")
            
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"crawler_{timestamp}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)


    
def get_keywords(keyword: str) -> list:   
    if keyword == "accept":
        unique_keywords = set(accept_words)  
        for lang_dict in words.values():
            for word in accept_words:
                if word in lang_dict:
                    unique_keywords.add(lang_dict[word])

        return list(unique_keywords) 

    return []


def scroll_down(page: Page):
    at_bottom = False
    page.wait_for_selector("body")
    while not at_bottom:
        page.evaluate(f"window.scrollBy(0, {300 + int(300 * random.random())})")
        
        at_bottom = page.evaluate(
            "(() => (window.scrollY + window.innerHeight + 100) > document.body.clientHeight)()"
        )
        
        time.sleep(0.5 + random.random())
        
        
def scroll_to_bottom(page: Page):
    page.wait_for_selector("body")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
