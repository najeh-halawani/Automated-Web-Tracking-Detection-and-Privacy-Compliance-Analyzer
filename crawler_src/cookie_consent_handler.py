'''
Author: Najeh Halawani
-----
Last Modified: Sunday, 2nd November 2025 7:35:16 pm
Modified By: Najeh Halawani
-----
'''
import re
import logging
from typing import Optional, List, Tuple
from playwright.sync_api import Page, Locator, Frame, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


class CookieConsentHandler:

    def __init__(self, accept_keywords: Optional[List[str]] = None, reject_keywords: Optional[List[str]] = None):
        
        if (accept_keywords is None) == (reject_keywords is None):
            raise ValueError("Either accept_keywords or reject_keywords must be provided")
        
        # Determine mode and initialize keywords
        if accept_keywords is not None:
            self.mode = "accept"
            self.keywords_set = {k.lower() for k in accept_keywords}
            escaped_keywords = [re.escape(w) for w in accept_keywords]
            self.partial_match_pattern = re.compile(
                r'\b(' + '|'.join(escaped_keywords) + r')\b',
                re.IGNORECASE
            )
        else:  # reject_keywords is not None
            self.mode = "reject"
            self.keywords_set = {k.lower() for k in reject_keywords}
            escaped_keywords = [re.escape(w) for w in reject_keywords]
            self.partial_match_pattern = re.compile(
                r'\b(' + '|'.join(escaped_keywords) + r')\b',
                re.IGNORECASE
            )

    def _is_valid_button_text(self, text: str) -> bool:
        if not text or len(text.strip()) < 2:
            return False
        alpha_chars = sum(c.isalpha() for c in text)
        if alpha_chars < 2:
            return False
        return True

    def _score_button_text(self, text: str) -> int:
        """
        Scores a button's text based on how likely it is to be a cookie accept/reject button.
        - Score 3 (High): Exact match.
        - Score 2 (Medium): Partial match on a short string.
        - Score 1 (Low): Partial match on a long string.
        - Score 0 (No Match): No keyword found.
        """
        normalized_text = text.strip().lower()

        # Score 3: Exact match (highest priority)
        if normalized_text in self.keywords_set and len(normalized_text) < 10:
            return 3
        elif normalized_text in self.keywords_set:
            return 2.5  # type: ignore
         
        # Check for partial matches
        if self.partial_match_pattern.search(normalized_text):
            # Score 2: Keyword found in a short text (likely a button label)
            if len(normalized_text) < 15:
                return 2
            # Score 1: Keyword found in a longer text (could be a false positive)
            else:
                return 1

        return 0

    def _find_and_score_buttons(self, context: Page | Frame) -> List[Tuple[int, Locator, str]]:
        """
        Find and score buttons based on the acept or reject mode.
        """
        candidates = []
        try:
            # Expanded selectors to be more comprehensive
            buttons = context.locator("button, a[role='button'], div[role='button'], input[type='submit'], input[type='button']").all()
        except PlaywrightTimeoutError:
            # If the context is empty or times out, return no candidates
            return []

        for button in buttons:
            try:
                if not button.is_visible(timeout=1000):
                    continue

                text = button.inner_text(timeout=1000).strip()

                if not self._is_valid_button_text(text):
                    continue

                score = self._score_button_text(text)
                if score > 0:
                    # Add the score, the button locator, and its text to our list
                    candidates.append((score, button, text))
            except Exception:
                # Ignore stale or inaccessible elements
                continue
        return candidates


    def _try_common_selectors(self, page: Page) -> bool:
        # We first try common button selectors for popular consent platforms based on crawler mode
        if self.mode == "accept":
            common_selectors = [
                # OneTrust
                "#onetrust-accept-btn-handler", "button#onetrust-accept-btn-handler",
                # Cookiebot
                "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll", "a#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
                # Cookie Information
                "#cookie-information-template-wrapper button.cookie-information-accept-all",
                # Termly
                "#termly-code-snippet-support button[data-tid='banner-accept']",
                # Didomi
                "#didomi-notice-agree-button", "button#didomi-notice-agree-button",
                # Osano
                ".osano-cm-accept-all", "button.osano-cm-accept-all",
                # TrustArc
                "#truste-consent-button",
                # Quantcast
                "button[data-testid='qc-cmp2-ui-button'][mode='primary']"
            ]
        elif self.mode == "reject":  # reject mode
            common_selectors = [
                # OneTrust
                "#onetrust-reject-all-handler", "button#onetrust-reject-all-handler",
                # Cookiebot
                "#CybotCookiebotDialogBodyLevelButtonLevelOptinDeclineAll",
                "a#CybotCookiebotDialogBodyLevelButtonLevelOptinDeclineAll",
                # Didomi
                "#didomi-notice-disagree-button", "button#didomi-notice-disagree-button",
                # Osano
                ".osano-cm-deny-all", "button.osano-cm-deny-all",
                # TrustArc
                "#truste-consent-required",
                # Quantcast
                "button[data-testid='qc-cmp2-ui-button'][mode='secondary']",
                # Cookie Information
                "#cookie-information-template-wrapper button.cookie-information-reject-all",
            ]

        for selector in common_selectors:
            try:
                button = page.locator(selector).first
                if button.is_visible(timeout=3000):
                    button_text = button.inner_text(timeout=1000)
                    logger.info(f"Found common {self.mode} selector: {selector} with text: '{button_text}'")
                    button.click(timeout=3000)
                    logger.info(f"Successfully clicked {self.mode} button via common selector: {selector}")
                    return True
            except Exception:
                # Silently continue to next selector
                continue

        return False

    def accept_cookies(self, page: Page) -> bool:
        logger.info(f"Attempting to accept cookies on: {page.url}")

        # Strategy 1: Try common selectors first (fastest and most reliable)
        if self._try_common_selectors(page):
            return True

        # Strategy 2: Collect, Score, and Decide
        all_candidates = []

        logger.info("Searching for buttons on the main page...")
        all_candidates.extend(self._find_and_score_buttons(page))

        # Find and score buttons within all iframes
        try:
            frames = page.frames
            logger.info(f"Found {len(frames)} frames. Searching for buttons in each...")
            for frame in frames:
                all_candidates.extend(self._find_and_score_buttons(frame))
        except Exception as e:
            logger.error(f"An error occurred while processing frames: {e}")

        if not all_candidates:
            logger.warning(f"Could not find any potential cookie accept buttons on: {page.url}")
            return False

        for score, _, text in all_candidates:
            logger.info(f"Found candidate button with score {score}: '{text}'")
            
        # Sort candidates by score in descending order (highest score first)
        all_candidates.sort(key=lambda x: x[0], reverse=True)

        # The best candidate is the first one in the sorted list
        best_score, best_button, best_text = all_candidates[0]

        logger.info(f"Choosing the best match (Score: {best_score}): '{best_text}'")
        try:
            best_button.click(timeout=5000)
            logger.info(f"Successfully clicked button: '{best_text}'")
            return True
        except Exception as e:
            logger.error(f"Failed to click the chosen button '{best_text}': {e}")
            return False

    def reject_cookies(self, page: Page) -> bool:
        """
        Attempt to reject cookies on the page.
        Uses the same strategy as accept_cookies but with reject keywords.
        """
        logger.info(f"Attempting to reject cookies on: {page.url}")

        # Strategy 1: Try common selectors first (fastest and most reliable)
        if self._try_common_selectors(page):
            return True

        # Strategy 2: Collect, Score, and Decide
        all_candidates = []

        logger.info("Searching for reject buttons on the main page...")
        all_candidates.extend(self._find_and_score_buttons(page))

        # Find and score buttons within all iframes
        try:
            frames = page.frames
            logger.info(f"Found {len(frames)} frames. Searching for reject buttons in each...")
            for frame in frames:
                all_candidates.extend(self._find_and_score_buttons(frame))
        except Exception as e:
            logger.error(f"An error occurred while processing frames: {e}")

        if not all_candidates:
            logger.warning(f"Could not find any potential cookie reject buttons on: {page.url}")
            return False

        for score, _, text in all_candidates:
            logger.info(f"Found candidate reject button with score {score}: '{text}'")
            
        # Sort candidates by score in descending order (highest score first)
        all_candidates.sort(key=lambda x: x[0], reverse=True)

        # The best candidate is the first one in the sorted list
        best_score, best_button, best_text = all_candidates[0]

        logger.info(f"Choosing the best reject match (Score: {best_score}): '{best_text}'")
        try:
            best_button.click(timeout=5000)
            logger.info(f"Successfully clicked reject button: '{best_text}'")
            return True
        except Exception as e:
            logger.error(f"Failed to click the chosen reject button '{best_text}': {e}")
            return False


def accept_cookies(page: Page, accept_keywords: List[str]) -> bool:
    handler = CookieConsentHandler(accept_keywords=accept_keywords)
    return handler.accept_cookies(page)


def reject_cookies(page: Page, reject_keywords: List[str]) -> bool:
    handler = CookieConsentHandler(reject_keywords=reject_keywords)
    return handler.reject_cookies(page)