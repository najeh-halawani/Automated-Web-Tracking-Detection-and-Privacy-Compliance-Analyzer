'''
Author: Najeh Halawani
-----
Last Modified: Sunday, 2nd November 2025 6:41:22 pm
Modified By: Najeh Halawani
-----
'''

import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from time import sleep
from utils import get_keywords, scroll_to_bottom
from pathlib import Path

from cookie_consent_handler import CookieConsentHandler, accept_cookies

logger = logging.getLogger(__name__)


def run_accept(domain: str):
    logger.info(f"Starting accept crawl for: {domain}")
    
    output_dir = Path("./crawl_data_accept")
    output_dir.mkdir(exist_ok=True)
    
    accept_keywords = get_keywords("accept")
    logger.info(f"Loaded {len(accept_keywords)} accept keywords from words.json")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled', 
            ]
        )
        
        context = browser.new_context(
            # viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            record_har_path=f"{output_dir}/{domain}.har",
            record_video_dir=str(output_dir)
        )
        
        page = context.new_page()
        
        try:
            logger.info(f"Navigating to: https://{domain}")
            response = page.goto(
                f"https://{domain}",
                wait_until="domcontentloaded",
                timeout=30000
            )
            
            if response is None:
                logger.error(f"Failed to load page: {domain}")
                return
            
            logger.info(f"Page loaded with status: {response.status}")
            
            logger.info("Waiting 10 seconds for page to load completely...")
            sleep(3)
            
            logger.info("Taking pre-consent screenshot...")
            page.screenshot(
                path=f"{output_dir}/{domain}_pre_consent.png",
                full_page=True,
                timeout=10000
            )
            
            logger.info("Attempting to accept cookies...")
            consent_accepted = accept_cookies(page, accept_keywords)
            
            if consent_accepted:
                logger.info(f"Successfully accepted cookies on {domain}")
                sleep(2)
            else:
                logger.warning(f"No consent dialog found or unable to accept on {domain}")
                sleep(1)
            
            logger.info("Taking post-consent screenshot...")
            page.screenshot(
                path=f"{output_dir}/{domain}_post_consent.png",
                full_page=True,
                timeout=10000
            )
            
            logger.info("Scrolling to bottom of page...")
            scroll_to_bottom(page)
            sleep(2)
            
            logger.info(f"Successfully completed crawl for: {domain}")
            
        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout error on {domain}: {e}")
        except Exception as e:
            logger.error(f"Error crawling {domain}: {e}", exc_info=True)
        finally:
            try:
                context.close()
                browser.close()
            except Exception as e:
                logger.error(f"Error closing browser: {e}")


def run_reject(domain: str):

    logger.info(f"Starting reject crawl for: {domain}")
    # TODO: Implement reject logic similar to accept
    pass


def run_block(domain: str):
    logger.info(f"Starting block crawl for: {domain}")
    # TODO: Implement block logic
    pass