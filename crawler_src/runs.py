
import json
import logging
from pathlib import Path
from time import sleep

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


from cookie_consent_handler import (
    accept_cookies,
    reject_cookies,
    detect_consent_banner,
    detect_accept_button,
    detect_subscribe_button,
    detect_essentials_only_button,
    accept_essentials_only,
)
from utils import (
    get_keywords,
    get_setting_keywords,
    get_save_setting_keywords,
    get_essentials_only_keywords,
    scroll_to_bottom,
)
from crawlers.crawler_block import (
    load_disconnect_blocklist,
    build_blocked_etld1_set,
    _create_block_context,
)

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

            logger.info("Waiting 10 seconds for page to load completely...")
            sleep(10)

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
                logger.warning(
                    f"No consent dialog found or unable to accept on {domain}"
                )
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
                    json.dumps(
                        {"domain": domain, "writes": cookie_log},
                        ensure_ascii=False,
                        indent=2,
                    ),
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
    output_dir = Path("./crawl_data_reject")
    output_dir.mkdir(exist_ok=True)

    reject_keywords = get_keywords("reject")
    accept_keywords = get_keywords("accept")
    setting_keywords = get_setting_keywords()
    save_keywords = get_save_setting_keywords()
    essentials_only_keywords = get_essentials_only_keywords()
    logger.info(
        "Loaded %s reject keywords, %s accept keywords, %s setting keywords, %s save keywords, and %s essentials-only keywords",
        len(reject_keywords),
        len(accept_keywords),
        len(setting_keywords),
        len(save_keywords),
        len(essentials_only_keywords),
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            record_har_path=f"{output_dir}/{domain}.har",
            record_video_dir=str(output_dir),
        )

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

            logger.info("Waiting 10 seconds for page to load completely...")
            sleep(10)

            logger.info("Taking pre-consent screenshot...")
            try:
                page.screenshot(
                    path=f"{output_dir}/{domain}_pre_consent.png",
                    full_page=True,
                    timeout=5000,
                )
            except PlaywrightTimeoutError:
                logger.warning(f"Screenshot timeout on {domain} (pre-consent), continuing...")
            except Exception as exc:
                logger.warning(f"Error taking pre-consent screenshot on {domain}: {exc}")

            logger.info("Attempting to reject cookies...")
            consent_rejected = reject_cookies(
                page,
                reject_keywords,
                setting_keywords=setting_keywords,
                save_keywords=save_keywords,
            )

            if consent_rejected:
                logger.info(f"Successfully rejected cookies on {domain}")
                sleep(5)
            else:
                subscribe_button_available = detect_subscribe_button(page)
                accept_button_available = detect_accept_button(page, accept_keywords)

                if subscribe_button_available and accept_button_available:
                    logger.warning(
                        "Subscribe + accept scenario detected on %s: banner has subscribe and accept buttons, reject option unavailable",
                        domain,
                    )
                    logger.info("Not attempting mandatory accept fallback for subscribe + accept sites")
                    sleep(2)
                else:
                    banner_exists = detect_consent_banner(page)

                    if banner_exists and accept_button_available:
                        logger.warning(
                            "Mandatory accept scenario detected on %s: banner exists but reject option unavailable",
                            domain,
                        )
                        logger.info("Checking for essentials-only option...")
                        essentials_only_available = detect_essentials_only_button(
                            page, essentials_only_keywords
                        )

                        if essentials_only_available:
                            logger.info(
                                "Essentials-only option found, attempting to accept essential cookies only..."
                            )
                            essentials_accepted = accept_essentials_only(
                                page, essentials_only_keywords
                            )
                            if essentials_accepted:
                                logger.warning(
                                    f"Accepted essential cookies on {domain} (reject mode)"
                                )
                                sleep(2)
                            else:
                                logger.warning(
                                    f"Could not accept essential cookies, falling back to accept all on {domain}"
                                )
                                consent_accepted = accept_cookies(
                                    page, accept_keywords
                                )
                                if consent_accepted:
                                    logger.warning(
                                        f"Accepted all cookies as fallback on {domain} (reject mode)"
                                    )
                                    sleep(2)
                                else:
                                    logger.warning(
                                        f"Could not accept cookies as fallback on {domain}"
                                    )
                                    sleep(5)
                        else:
                            logger.info(
                                "No essentials-only option found, accepting all cookies as fallback (included in reject analysis)..."
                            )
                            consent_accepted = accept_cookies(page, accept_keywords)
                            if consent_accepted:
                                logger.warning(
                                    f"Accepted all cookies as fallback on {domain} (reject mode)"
                                )
                                sleep(2)
                            else:
                                logger.warning(
                                    f"Could not accept cookies as fallback on {domain}"
                                )
                                sleep(5)
                    elif not banner_exists:
                        logger.info(f"No consent banner detected on {domain} (auto-accept site)")
                        sleep(5)
                    else:
                        logger.warning(
                            f"Banner exists but no actionable buttons found on {domain}"
                        )
                        sleep(5)

            logger.info("Taking post-consent screenshot...")
            try:
                page.screenshot(
                    path=f"{output_dir}/{domain}_post_consent.png",
                    full_page=True,
                    timeout=5000,
                )
            except PlaywrightTimeoutError:
                logger.warning(f"Screenshot timeout on {domain} (post-consent), continuing...")
            except Exception as exc:
                logger.warning(f"Error taking post-consent screenshot on {domain}: {exc}")

            logger.info("Scrolling to bottom of page...")
            scroll_to_bottom(page)
            sleep(5)

            logger.info(f"Successfully completed reject crawl for: {domain}")

        except PlaywrightTimeoutError as err:
            logger.error(f"Timeout error on {domain}: {err}")
        except Exception as err:
            logger.error(f"Error crawling {domain}: {err}", exc_info=True)
        finally:
            try:
                cookie_log = page.evaluate("window.__cookieWrites || []")
                (output_dir / f"{domain}_cookie_writes.json").write_text(
                    json.dumps(
                        {"domain": domain, "writes": cookie_log},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except Exception as err:
                logger.error(f"Error saving cookie log: {err}")

            try:
                context.close()
                browser.close()
            except Exception as err:
                logger.error(f"Error closing browser: {err}")


# Run command: python -m crawler_src.crawl -m block -l crawler_src/site_list.csv
def run_block(
    domain: str, services_path: str | Path = "./crawler_src/disconnect_blocklist.json"
):
    """Run the Block crawler for a single domain.
    - Loads Disconnect services.json
    - Blocks requests to Advertising/Analytics/Social/Fingerprinting domains
    - Accepts consent (per assignment for block mode)
    - Captures HAR, video, pre/post screenshots, and client-side cookie writes
    """
    logger.info(f"Starting block crawl for: {domain}")
    output_dir = Path("./crawl_data_block")
    output_dir.mkdir(exist_ok=True)

    # Load blocklist
    services = load_disconnect_blocklist(services_path)
    blocked = build_blocked_etld1_set(services)
    logger.info(f"Blocklist domains (eTLD+1): {len(blocked)}")

    accept_keywords = get_keywords("accept")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context, page = _create_block_context(browser, output_dir, domain, blocked)

        try:
            logger.info(f"Navigating to: https://{domain}")
            response = page.goto(
                f"https://{domain}", wait_until="domcontentloaded", timeout=30000
            )
            if response is None:
                logger.error(f"Failed to load page: {domain}")
                return
            logger.info(f"Page loaded with status: {response.status}")

            logger.info("Waiting 7 seconds for page to settle...")
            sleep(7)

            logger.info("Taking pre-consent screenshot...")
            page.screenshot(
                path=str(output_dir / f"{domain}_pre_consent.png"),
                full_page=True,
                timeout=10000,
            )

            # In block mode: Accept all (assignment requirement)
            logger.info(
                "Attempting to accept cookies (block mode requires accept-all)..."
            )
            try:
                consent_accepted = accept_cookies(page, accept_keywords)
                if consent_accepted:
                    logger.info("Consent accepted.")
                else:
                    logger.warning("No consent dialog found or unable to accept.")
            except Exception as e:
                logger.warning(f"Consent handler error: {e}")

            logger.info("Taking post-consent screenshot...")
            page.screenshot(
                path=str(output_dir / f"{domain}_post_consent.png"),
                full_page=True,
                timeout=10000,
            )

            logger.info("Scrolling to bottom of page...")
            scroll_to_bottom(page)
            sleep(2)

            logger.info(f"Block crawl finished for: {domain}")

        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout on {domain}: {e}")
        except Exception as e:
            logger.error(f"Error crawling {domain}: {e}", exc_info=True)
        finally:
            # Persist any client-side cookie writes captured during the session.
            try:
                cookie_log = page.evaluate("window.__cookieWrites || []")
                (output_dir / f"{domain}_cookie_writes.json").write_text(
                    json.dumps(
                        {"domain": domain, "writes": cookie_log},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except Exception as e:
                logger.error(f"Error saving cookie log: {e}")

            try:
                context.close()
                browser.close()
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
