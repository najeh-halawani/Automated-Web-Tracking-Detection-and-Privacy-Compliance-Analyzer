'''
Author: Najeh Halawani
-----
Last Modified: Monday, 10th November 2025 12:00:00 pm
Modified By: Mikel Telleria
-----
'''

import json
import logging
from pathlib import Path
from time import sleep

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from crawler_src.cookie_consent_handler import CookieConsentHandler, accept_cookies, reject_cookies
from crawler_src.utils import get_keywords, scroll_to_bottom

logger = logging.getLogger(__name__)

# Run command: python -m crawler_src.crawl -m accept -l data/site_list.csv
def run_accept(domain: str):
    logger.info(f"Starting accept crawl for: {domain}")
    output_dir = Path("./crawl_data_accept")
    output_dir.mkdir(exist_ok=True)

    accept_keywords = get_keywords("accept")
    logger.info(f"Loaded {len(accept_keywords)} accept keywords from words.json")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        context = browser.new_context(
            # viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            record_har_path=f"{output_dir}/{domain}.har",
            record_video_dir=str(output_dir),
        )

        # Instrument document.cookie to log client-side writes.
        context.add_init_script(
            """
(() => {
  const { get, set } = Object.getOwnPropertyDescriptor(Document.prototype, "cookie");
  window.__cookieWrites = [];
  Object.defineProperty(document, "cookie", {
    configurable: true,
    enumerable: true,
    get() {
      return get.call(document);
    },
    set(value) {
      try {
        window.__cookieWrites.push({ value, time: Date.now() });
      } catch (err) {
        console.error("cookie instrumentation error", err);
      }
      return set.call(document, value);
    }
  });
})();
"""
        )

        page = context.new_page()

        try:
            logger.info(f"Navigating to: https://{domain}")
            response = page.goto(
                f"https://{domain}",
                wait_until="domcontentloaded",
                timeout=30000,
            )

            if response is None:
                logger.error(f"Failed to load page: {domain}")
                return

            logger.info(f"Page loaded with status: {response.status}")

            logger.info("Waiting 7 seconds for page to load completely...")
            sleep(7)

            logger.info("Taking pre-consent screenshot...")
            page.screenshot(
                path=f"{output_dir}/{domain}_pre_consent.png",
                full_page=True,
                timeout=10000,
            )

            logger.info("Attempting to accept cookies...")
            consent_accepted = accept_cookies(page, accept_keywords)

            if consent_accepted:
                logger.info(f"Successfully accepted cookies on {domain}")
                sleep(2)
            else:
                logger.warning(f"No consent dialog found or unable to accept on {domain}")
                sleep(1.5)

            logger.info("Taking post-consent screenshot...")
            page.screenshot(
                path=f"{output_dir}/{domain}_post_consent.png",
                full_page=True,
                timeout=10000,
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
                # Persist any client-side cookie writes captured during the session.
                cookie_log = page.evaluate("window.__cookieWrites || []")
                (output_dir / f"{domain}_cookie_writes.json").write_text(
                    json.dumps({"domain": domain, "writes": cookie_log}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception as e:
                logger.error(f"Error saving cookie log: {e}")

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