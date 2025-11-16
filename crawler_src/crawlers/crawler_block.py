import json
import logging
from pathlib import Path
from time import sleep

import tldextract
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from cookie_consent_handler import CookieConsentHandler, accept_cookies
from utils import get_keywords, scroll_to_bottom

from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# --- Disconnect blocklist helpers -------------------------------------------------
_REQUIRED_CATEGORIES = {
    "Advertising",
    "Analytics",
    "Social",
    "FingerprintingInvasive",
    "FingerprintingGeneral",
}

_tld = tldextract.TLDExtract(suffix_list_urls=None)


def _etld1(host: str) -> str:
    if not host:
        return ""
    ext = _tld(host)
    return (ext.registered_domain or host).lower()


def load_disconnect_blocklist(path: str | Path) -> dict:
    """Load Disconnect's services.json from a local path.
    Raises FileNotFoundError if not found.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Disconnect services.json not found at: {p}")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_blocked_etld1_set(services: dict) -> set[str]:
    """
    Support both:
      A) New schema: {"license": "...", "categories": { "Advertising": {...}, ... }}
         where each category maps to either:
           - dict of entities -> list[str domain], or
           - list[str domain]
      B) Old schema: { "Google": {"categories":[...], "properties":[...]} , ... }
    """
    blocked: set[str] = set()
    if not isinstance(services, dict):
        return blocked

    # ---- A) New schema: categories-first
    cats_obj = services.get("categories")
    if isinstance(cats_obj, dict):
        for cat_name, payload in cats_obj.items():
            if cat_name not in _REQUIRED_CATEGORIES:
                continue

            # payload can be a dict of entities -> [domains], or a flat list of domains
            if isinstance(payload, dict):
                iter_domain_lists = payload.values()
            elif isinstance(payload, list):
                iter_domain_lists = [payload]
            else:
                continue

            for domain_list in iter_domain_lists:
                if not isinstance(domain_list, (list, tuple)):
                    continue
                for host in domain_list:
                    if not host:
                        continue
                    host = str(host).lstrip("*.").strip()
                    et = _etld1(host)
                    if et:
                        blocked.add(et)
        return blocked

    # ---- B) Old schema: entities-first
    for _entity, entry in services.items():
        if not isinstance(entry, dict):
            continue
        cats = set(map(str, entry.get("categories", [])))
        if not (cats & _REQUIRED_CATEGORIES):
            continue
        for host in entry.get("properties", []):
            if not host:
                continue
            host = str(host).lstrip("*.").strip()
            et = _etld1(host)
            if et:
                blocked.add(et)

    return blocked


# --- Playwright context & routing -------------------------------------------------


def _make_block_route(blocked_etld1: set[str]):
    def handler(route, request):
        try:
            host = urlparse(request.url).hostname or ""
            et = _etld1(host)
            if et and et in blocked_etld1:
                return route.abort()
        except Exception:
            # Fail-open to avoid breaking navigation on parsing issues
            pass
        return route.continue_()

    return handler


def _create_block_context(
    browser, output_dir: Path, domain: str, blocked_etld1: set[str]
):
    """Create a Playwright context that records HAR/video and blocks tracking domains."""
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        record_har_path=str(output_dir / f"{domain}.har"),
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
    get() { return get.call(document); },
    set(value) {
      try { window.__cookieWrites.push({ value, time: Date.now() }); } catch (_) {}
      return set.call(document, value);
    }
  });
})();
"""
    )

    # Apply request blocking route
    context.route("**/*", _make_block_route(blocked_etld1))

    page = context.new_page()
    return context, page


# --- Public entrypoint ------------------------------------------------------------


def run_block(
    domain: str, services_path: str | Path = "./crawler_src/disconnect_blocklist.json"
):
    # Path can be changed to ./crawler_src/disconnect_blocklist.json
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

            logger.info("Waiting 10 seconds for page to settle...")
            sleep(10)

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
