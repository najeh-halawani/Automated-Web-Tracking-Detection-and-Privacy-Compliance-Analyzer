'''
Author: Najeh Halawani
-----
Last Modified: Sunday, 2nd November 2025 7:35:16 pm
Modified By: Najeh Halawani
-----
Last Modified: Wednesday, 15th November 2025 03:18:34 am
    Added reject logic
Modified By: Rahul Deiv
-----
'''
import re
import logging
from typing import Optional, List, Tuple
from playwright.sync_api import Page, Locator, Frame, TimeoutError as PlaywrightTimeoutError
from time import sleep

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

    def _score_button_text(self, text: str, keywords_set: Optional[set] = None, pattern: Optional[re.Pattern] = None) -> int:
        """
        Scores a button's text based on how likely it is to match the given keywords.
        - Score 3.5 (Highest): "reject all purposes" (most specific reject option)
        - Score 3 (High): Exact match with short keyword.
        - Score 2.5 (High): Exact match with longer keyword.
        - Score 2 (Medium): Partial match on a short string.
        - Score 1 (Low): Partial match on a longer string.
        - Score 0 (No Match): No keyword found.
        
        Args:
            text: Button text to score
            keywords_set: Optional keyword set to match against (defaults to handler's keywords)
            pattern: Optional regex pattern to match against (defaults to handler's pattern)
        """
        normalized_text = text.strip().lower()
        
        # Use provided keywords/pattern or fall back to handler's own
        keywords = keywords_set if keywords_set is not None else self.keywords_set
        match_pattern = pattern if pattern is not None else self.partial_match_pattern
        
        if not keywords:
            return 0

        # Score 3.5: "reject all purposes" - highest priority (most specific reject option)
        if "reject all purposes" in normalized_text or "reject all purpose" in normalized_text:
            return 3.5  # type: ignore

        # Score 3: Exact match with short keyword (highest priority)
        if normalized_text in keywords and len(normalized_text) < 10:
            return 3
        # Score 2.5: Exact match with longer keyword
        elif normalized_text in keywords:
            return 2.5  # type: ignore
         
        # Check for partial matches
        if match_pattern and match_pattern.search(normalized_text):
            # Score 2: Keyword found in a short text (likely a button label)
            if len(normalized_text) < 15:
                return 2
            # Score 1: Keyword found in a longer text (could be a false positive)
            else:
                return 1

        return 0

    def _find_and_score_buttons(self, context: Page | Frame) -> List[Tuple[int, Locator, str]]:
        """
        Find and score buttons based on the accept or reject mode.
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
        """
        Try common button selectors for popular consent platforms.
        Works for both accept and reject modes.
        """
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
        elif self.mode == "reject":  # reject mode - common selectors for reject buttons
            common_selectors = [
                # OneTrust
                "#onetrust-reject-all-handler", "button#onetrust-reject-all-handler",
                # Cookiebot
                "#CybotCookiebotDialogBodyLevelButtonLevelOptinDeclineAll", "a#CybotCookiebotDialogBodyLevelButtonLevelOptinDeclineAll",
                # Cookie Information
                "#cookie-information-template-wrapper button.cookie-information-decline-all",
                # Termly
                "#termly-code-snippet-support button[data-tid='banner-reject']",
                # Didomi
                "#didomi-notice-reject-button", "button#didomi-notice-reject-button",
                # Osano
                ".osano-cm-deny-all", "button.osano-cm-deny-all",
                # TrustArc
                "#truste-consent-reject",
                # Quantcast
                "button[data-testid='qc-cmp2-ui-button'][mode='secondary']"
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

    def _detect_consent_banner(self, page: Page) -> bool:
        """
        Detect if a consent banner exists on the page.
        Checks for common consent banner selectors and keywords.
        """
        # Common consent banner selectors
        banner_selectors = [
            # OneTrust
            "#onetrust-banner-sdk", "#onetrust-policy",
            # Cookiebot
            "#CybotCookiebotDialog", "#CookiebotDialog",
            # Cookie Information
            "#cookie-information-template-wrapper",
            # Termly
            "#termly-code-snippet-support",
            # Didomi
            "#didomi-popup", "#didomi-notice",
            # Osano
            ".osano-cm-dialog", ".osano-cm-info-dialog-open",
            # TrustArc
            "#truste-consent-track",
            # Quantcast
            "[data-testid='qc-cmp2-ui']",
            # Generic
            "[id*='cookie']", "[class*='cookie']", "[id*='consent']", "[class*='consent']",
            "[id*='gdpr']", "[class*='gdpr']", "[id*='privacy']", "[class*='privacy']"
        ]
        
        # Check for visible banner elements
        for selector in banner_selectors:
            try:
                element = page.locator(selector).first
                if element.is_visible(timeout=1000):
                    return True
            except Exception:
                continue
        
        # Check in iframes
        try:
            for frame in page.frames:
                for selector in banner_selectors:
                    try:
                        element = frame.locator(selector).first
                        if element.is_visible(timeout=1000):
                            return True
                    except Exception:
                        continue
        except Exception:
            pass
        
        return False

    def _detect_accept_button(self, page: Page, accept_keywords: List[str]) -> bool:
        """
        Detect if an accept button is available on the page.
        Uses accept keywords to find potential accept buttons.
        """
        # Create temporary handler with accept keywords for detection
        temp_handler = CookieConsentHandler(accept_keywords=accept_keywords)
        
        # Check common accept selectors
        accept_selectors = [
            "#onetrust-accept-btn-handler", "button#onetrust-accept-btn-handler",
            "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
            "#didomi-notice-agree-button", "button#didomi-notice-agree-button",
            ".osano-cm-accept-all", "button.osano-cm-accept-all",
            "#truste-consent-button",
        ]
        
        for selector in accept_selectors:
            try:
                button = page.locator(selector).first
                if button.is_visible(timeout=1000):
                    return True
            except Exception:
                continue
        
        # Check for accept buttons using keyword matching
        try:
            buttons = page.locator("button, a[role='button'], div[role='button'], input[type='submit'], input[type='button']").all()
            for button in buttons:
                try:
                    if not button.is_visible(timeout=500):
                        continue
                    text = button.inner_text(timeout=500).strip().lower()
                    if temp_handler._score_button_text(text) > 0:
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        
        # Check in iframes
        try:
            for frame in page.frames:
                for selector in accept_selectors:
                    try:
                        button = frame.locator(selector).first
                        if button.is_visible(timeout=1000):
                            return True
                    except Exception:
                        continue
                
                try:
                    buttons = frame.locator("button, a[role='button'], div[role='button'], input[type='submit'], input[type='button']").all()
                    for button in buttons:
                        try:
                            if not button.is_visible(timeout=500):
                                continue
                            text = button.inner_text(timeout=500).strip().lower()
                            if temp_handler._score_button_text(text) > 0:
                                return True
                        except Exception:
                            continue
                except Exception:
                    continue
        except Exception:
            pass
        
        return False

    def _detect_essentials_only_button(self, page: Page, essentials_only_keywords: List[str]) -> bool:
        """
        Detect if an essentials only button is available on the page.
        Uses essentials only keywords to find potential buttons.
        """
        # Create temporary handler with essentials only keywords for detection
        temp_handler = CookieConsentHandler(accept_keywords=essentials_only_keywords)
        
        # Check for essentials only buttons using keyword matching
        try:
            buttons = page.locator("button, a[role='button'], div[role='button'], input[type='submit'], input[type='button']").all()
            for button in buttons:
                try:
                    if not button.is_visible(timeout=500):
                        continue
                    text = button.inner_text(timeout=500).strip().lower()
                    if temp_handler._score_button_text(text) > 0:
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        
        # Check in iframes
        try:
            for frame in page.frames:
                try:
                    buttons = frame.locator("button, a[role='button'], div[role='button'], input[type='submit'], input[type='button']").all()
                    for button in buttons:
                        try:
                            if not button.is_visible(timeout=500):
                                continue
                            text = button.inner_text(timeout=500).strip().lower()
                            if temp_handler._score_button_text(text) > 0:
                                return True
                        except Exception:
                            continue
                except Exception:
                    continue
        except Exception:
            pass
        
        return False

    def accept_essentials_only(self, page: Page, essentials_only_keywords: List[str]) -> bool:
        """
        Attempt to accept only essential/necessary cookies.
        Uses essentials only keywords to find and click the appropriate button.
        """
        logger.info(f"Attempting to accept essential cookies only on: {page.url}")
        
        # Collect, Score, and Decide
        all_candidates = []
        
        logger.info("Searching for essentials only buttons on the main page...")
        temp_handler = CookieConsentHandler(accept_keywords=essentials_only_keywords)
        all_candidates.extend(temp_handler._find_and_score_buttons(page))
        
        # Find and score buttons within all iframes
        try:
            frames = page.frames
            logger.info(f"Found {len(frames)} frames. Searching for essentials only buttons in each...")
            for frame in frames:
                all_candidates.extend(temp_handler._find_and_score_buttons(frame))
        except Exception as e:
            logger.error(f"An error occurred while processing frames: {e}")
        
        if not all_candidates:
            logger.warning(f"Could not find any potential essentials only buttons on: {page.url}")
            return False
        
        for score, _, text in all_candidates:
            logger.info(f"Found candidate essentials only button with score {score}: '{text}'")
        
        # Sort candidates by score in descending order (highest score first)
        all_candidates.sort(key=lambda x: x[0], reverse=True)
        
        # The best candidate is the first one in the sorted list
        best_score, best_button, best_text = all_candidates[0]
        
        logger.info(f"Choosing the best essentials only match (Score: {best_score}): '{best_text}'")
        try:
            best_button.click(timeout=5000)
            logger.info(f"Successfully clicked essentials only button: '{best_text}'")
            return True
        except Exception as e:
            logger.error(f"Failed to click the chosen essentials only button '{best_text}': {e}")
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

    def _find_settings_button(self, context: Page | Frame, setting_keywords: List[str]) -> Optional[Locator]:
        """
        We use this to find a settings/customize button using setting keywords.
        """
        setting_keywords_set = {k.lower() for k in setting_keywords}
        escaped_keywords = [re.escape(w) for w in setting_keywords]
        setting_pattern = re.compile(
            r'\b(' + '|'.join(escaped_keywords) + r')\b',
            re.IGNORECASE
        )

        try:
            buttons = context.locator("button, a[role='button'], div[role='button'], input[type='submit'], input[type='button']").all()
        except PlaywrightTimeoutError:
            return None

        for button in buttons:
            try:
                if not button.is_visible(timeout=0):
                    continue

                text = button.inner_text(timeout=0).strip().lower()
                if not self._is_valid_button_text(text):
                    continue

                # Check for exact or partial match with setting keywords
                if text in setting_keywords_set or setting_pattern.search(text):
                    logger.info(f"Found settings button: '{text}'")
                    return button
            except Exception:
                continue

        return None

    def _find_reject_in_settings(self, context: Page | Frame) -> Optional[Locator]:
        """
        We use this to find a reject/essential-only button in the settings dialog.
        First tries get_by_role using reject keywords, then falls back to
        JavaScript-based text search for faster searching.
        """
        # First, try get_by_role using reject keywords (semantic and reliable)
        reject_keywords = list(self.keywords_set)
        for keyword in reject_keywords:
            try:
                button = context.get_by_role("button", name=keyword, exact=False)
                if button.is_visible(timeout=500):
                    # Verify the visible text matches our reject keywords with high score
                    button_text = button.inner_text(timeout=500).strip()
                    if button_text:
                        score = self._score_button_text(button_text)
                        # Only accept high scores (2.5 or higher) to avoid false positives
                        if score >= 2.5:
                            logger.info(f"Found reject button in settings via get_by_role: '{keyword}' (text: '{button_text}', score: {score})")
                            return button
            except Exception:
                continue
        
        # Fallback: Use JavaScript to get all button texts at once (much faster)
        try:
            button_data = context.evaluate("""
                () => {
                    const buttons = Array.from(document.querySelectorAll('button, a[role="button"], div[role="button"], input[type="submit"], input[type="button"]'));
                    return buttons.slice(0, 200).map((btn, index) => {
                        const style = window.getComputedStyle(btn);
                        const isVisible = style.display !== 'none' && 
                                         style.visibility !== 'hidden' && 
                                         style.opacity !== '0' &&
                                         btn.offsetWidth > 0 && 
                                         btn.offsetHeight > 0;
                        return {
                            index: index,
                            text: btn.innerText?.trim() || btn.textContent?.trim() || '',
                            visible: isVisible
                        };
                    });
                }
            """)
            
            candidates = []
            for btn_data in button_data:
                if not btn_data['visible']:
                    continue
                
                text = btn_data['text']
                if not text or not self._is_valid_button_text(text):
                    continue
                
                score = self._score_button_text(text)
                if score > 0:
                    candidates.append((score, btn_data['index'], text))
            
            if not candidates:
                return None
            
            # Sort by score and return the best match
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_index, best_text = candidates[0]
            logger.info(f"Found reject button in settings (Score: {best_score}): '{best_text}'")
            # Get the actual button locator for this index
            buttons = context.locator("button, a[role='button'], div[role='button'], input[type='submit'], input[type='button']").all()
            if best_index < len(buttons):
                return buttons[best_index]
            return None
            
        except Exception as e:
            logger.debug(f"Error in JavaScript-based button search: {e}")
            return None

    def _find_save_button(self, context: Page | Frame, save_keywords: List[str]) -> Optional[Locator]:
        """
        Find a save/confirm/apply button in the settings dialog.
        First tries get_by_role using keywords from words.json, then falls back to
        JavaScript-based text search for faster searching.
        """
        save_keywords_set = {k.lower() for k in save_keywords}
        escaped_keywords = [re.escape(w) for w in save_keywords]
        save_pattern = re.compile(
            r'\b(' + '|'.join(escaped_keywords) + r')\b',
            re.IGNORECASE
        )

        # First, try get_by_role using keywords from words.json (semantic and reliable)
        for name in save_keywords:
            try:
                button = context.get_by_role("button", name=name, exact=False)
                if button.is_visible(timeout=500):
                    # Verify the visible text matches our save keywords with high score to avoid false positives
                    button_text = button.inner_text(timeout=500).strip()
                    if button_text:
                        score = self._score_button_text(button_text, keywords_set=save_keywords_set, pattern=save_pattern)
                        # Only accept high scores (2.5 or higher) to avoid false positives
                        if score >= 2.5:
                            logger.info(f"Found save button via get_by_role: '{name}' (text: '{button_text}', score: {score})")
                            return button
            except Exception:
                continue

        try:
            # Use JavaScript to get all button texts and accessible names at once (much faster)
            button_data = context.evaluate("""
                () => {
                    const buttons = Array.from(document.querySelectorAll('button, a[role="button"], div[role="button"], input[type="submit"], input[type="button"]'));
                    return buttons.slice(0, 200).map((btn, index) => {
                        const style = window.getComputedStyle(btn);
                        const isVisible = style.display !== 'none' && 
                                         style.visibility !== 'hidden' && 
                                         style.opacity !== '0' &&
                                         btn.offsetWidth > 0 && 
                                         btn.offsetHeight > 0;
                        const text = btn.innerText?.trim() || btn.textContent?.trim() || '';
                        return {
                            index: index,
                            text: text,
                            visible: isVisible
                        };
                    });
                }
            """)
            
            candidates = []
            for btn_data in button_data:
                if not btn_data['visible']:
                    continue
                
                text = btn_data.get('text', '')
                if not text or not self._is_valid_button_text(text):
                    continue
                
                score = self._score_button_text(text, keywords_set=save_keywords_set, pattern=save_pattern)
                # Only accept high scores (2.5 or higher) to avoid false positives
                if score >= 2.5:
                    candidates.append((score, btn_data['index'], text))
            
            if not candidates:
                return None
            
            # Sort by score and return the best match
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_index, best_text = candidates[0]
            logger.info(f"Found save/confirm button (Score: {best_score}): '{best_text}'")
            # Get the actual button locator for this index
            buttons = context.locator("button, a[role='button'], div[role='button'], input[type='submit'], input[type='button']").all()
            if best_index < len(buttons):
                return buttons[best_index]
            return None
            
        except Exception as e:
            logger.debug(f"Error in JavaScript-based button search: {e}")
            return None

    def _try_multi_step_reject(self, page: Page, setting_keywords: List[str], save_keywords: List[str]) -> bool:
        """
        Multi-step reject flow: settings button → reject in settings → save.
        """
        logger.info("Attempting multi-step reject flow...")

        # Step 1: Find and click settings/customize button
        settings_button = None
        
        # Search in main page
        settings_button = self._find_settings_button(page, setting_keywords)
        
        # If not found, search in iframes
        if not settings_button:
            try:
                frames = page.frames
                for frame in frames:
                    settings_button = self._find_settings_button(frame, setting_keywords)
                    if settings_button:
                        break
            except Exception as e:
                logger.debug(f"Error searching frames for settings button: {e}")

        if not settings_button:
            logger.debug("No settings/customize button found for multi-step flow")
            return False

        try:
            settings_button_text = settings_button.inner_text(timeout=1000).strip()
            logger.info(f"Clicking settings button: '{settings_button_text}'")
            settings_button.click(timeout=5000)
            sleep(2)  # Wait for settings dialog to open
        except Exception as e:
            logger.warning(f"Failed to click settings button: {e}")
            return False

        # Step 2: Find and click reject/essential-only button in settings
        reject_button = None
        
        # Wait a bit more and check for new frames that might have appeared
        sleep(0.5)
        
        # Search in main page (settings dialog might be in main page)
        reject_button = self._find_reject_in_settings(page)
        
        # If not found, search in iframes
        if not reject_button:
            try:
                frames = page.frames
                for frame in frames:
                    reject_button = self._find_reject_in_settings(frame)
                    if reject_button:
                        break
            except Exception as e:
                logger.debug(f"Error searching frames for reject button: {e}")

        if not reject_button:
            logger.warning("Settings dialog opened but no reject button found")
            return False

        try:
            reject_button_text = reject_button.inner_text(timeout=1000).strip()
            logger.info(f"Clicking reject button in settings: '{reject_button_text}'")
            reject_button.click(timeout=5000)
            sleep(2)  # Wait for selection to register and UI to update (save button may appear)
        except Exception as e:
            logger.warning(f"Failed to click reject button in settings: {e}")
            return False

        # Step 3: Find and click save/confirm button (if it exists)
        # Some sites auto-apply settings after reject, so save button is optional
        # The save button may appear after clicking reject, so we wait and then search
        save_button = None
        
        # Wait for save button to appear (it may be dynamically added after clicking reject)
        sleep(2)
        
        # Re-get frames in case new ones appeared after clicking reject
        try:
            frames = page.frames
        except Exception:
            frames = []
        
        # Search in iframes first (save button is likely in the same dialog frame)
        if not save_button:
            try:
                for frame in frames:
                    save_button = self._find_save_button(frame, save_keywords)
                    if save_button:
                        break
            except Exception as e:
                logger.debug(f"Error searching frames for save button: {e}")
        
        # If not found in frames, search in main page
        if not save_button:
            save_button = self._find_save_button(page, save_keywords)

        if save_button:
            # Save button exists, click it
            try:
                save_button_text = save_button.inner_text(timeout=1000).strip()
                logger.info(f"Clicking save/confirm button: '{save_button_text}'")
                save_button.click(timeout=5000)
                logger.info("Successfully completed multi-step reject flow")
                return True
            except Exception as e:
                logger.warning(f"Failed to click save/confirm button: {e}")
                return False
        else:
            # No save button found - settings might auto-apply or dialog auto-closes
            logger.info("No save/confirm button found - settings may auto-apply after reject")
            logger.info("Successfully completed multi-step reject flow (auto-applied)")
            return True

    def reject_cookies(self, page: Page, setting_keywords: Optional[List[str]] = None, save_keywords: Optional[List[str]] = None) -> bool:
        """
        Attempt to reject cookies on the page.
        Uses multiple strategies:
        1. Try direct reject button (keyword-based) first
        2. Try multi-step flow (settings → reject → save) as fallback
        3. Try common selectors as last resort fallback
        """
        logger.info(f"Attempting to reject cookies on: {page.url}")

        # Strategy 1: Try direct reject button (keyword-based) first
        all_candidates = []

        logger.info("Searching for direct reject buttons on the main page...")
        all_candidates.extend(self._find_and_score_buttons(page))

        # Find and score buttons within all iframes
        try:
            frames = page.frames
            logger.info(f"Found {len(frames)} frames. Searching for reject buttons in each...")
            for frame in frames:
                all_candidates.extend(self._find_and_score_buttons(frame))
        except Exception as e:
            logger.error(f"An error occurred while processing frames: {e}")

        if all_candidates:
            for score, _, text in all_candidates:
                logger.info(f"Found candidate reject button with score {score}: '{text}'")
                
            # Sort candidates by score in descending order (highest score first)
            all_candidates.sort(key=lambda x: x[0], reverse=True)

            # The best candidate is the first one in the sorted list
            best_score, best_button, best_text = all_candidates[0]

            logger.info(f"Choosing the best reject match (Score: {best_score}): '{best_text}'")
            try:
                best_button.click(timeout=5000)
                logger.info(f"Successfully clicked direct reject button: '{best_text}'")
                return True
            except Exception as e:
                logger.warning(f"Failed to click the chosen reject button '{best_text}': {e}")

        # Strategy 2: Try multi-step flow as fallback (if direct reject failed)
        if setting_keywords and save_keywords:
            logger.info("Direct reject failed, attempting multi-step reject flow...")
            if self._try_multi_step_reject(page, setting_keywords, save_keywords):
                logger.info("Successfully rejected via multi-step flow")
                return True

        # Strategy 3: Try common selectors as last resort fallback
        if self._try_common_selectors(page):
            logger.info("Successfully rejected via common selectors (fallback)")
            return True

        logger.warning(f"Could not find any way to reject cookies on: {page.url}")
        return False


def accept_cookies(page: Page, accept_keywords: List[str]) -> bool:
    handler = CookieConsentHandler(accept_keywords=accept_keywords)
    return handler.accept_cookies(page)


def reject_cookies(page: Page, reject_keywords: List[str], setting_keywords: Optional[List[str]] = None, save_keywords: Optional[List[str]] = None) -> bool:
    handler = CookieConsentHandler(reject_keywords=reject_keywords)
    return handler.reject_cookies(page, setting_keywords=setting_keywords, save_keywords=save_keywords)


def detect_consent_banner(page: Page) -> bool:
    """
    Detect if a consent banner exists on the page.
    """
    handler = CookieConsentHandler(accept_keywords=["accept"])  # Dummy keywords for initialization
    return handler._detect_consent_banner(page)


def detect_accept_button(page: Page, accept_keywords: List[str]) -> bool:
    """
    Detect if an accept button is available on the page.
    """
    handler = CookieConsentHandler(accept_keywords=accept_keywords)
    return handler._detect_accept_button(page, accept_keywords)


def detect_subscribe_button(page: Page) -> bool:
    """
    Detect if a subscribe button/link is available on the page.
    Only checks within consent containers to avoid false positives (e.g., video CTAs, newsletter signups).
    Falls back to broad search if not found in consent containers.
    """
    subscribe_keywords = [
        "subscribe", "s'abonner", "abonner", "abonnieren", "abbonati", 
        "suscribirse", "inschrijven", "inscrever", "подписаться"
    ]
    
    # Common consent container selectors (same as used in _detect_consent_banner)
    consent_container_selectors = [
        # OneTrust
        "#onetrust-banner-sdk", "#onetrust-policy", "#onetrust-consent-sdk",
        # Cookiebot
        "#CybotCookiebotDialog", "#CookiebotDialog",
        # Didomi
        "#didomi-popup", "#didomi-notice",
        # Osano
        ".osano-cm-dialog", ".osano-cm-info-dialog-open",
        # TrustArc
        "#truste-consent-track",
        # Quantcast
        "[data-testid='qc-cmp2-ui']",
        # Generic
        "[id*='cookie']", "[class*='cookie']", "[id*='consent']", "[class*='consent']",
        "[id*='gdpr']", "[class*='gdpr']", "[id*='privacy']", "[class*='privacy']"
    ]
    
    try:
        # First, check within consent containers (strict check)
        for container_selector in consent_container_selectors:
            try:
                container = page.locator(container_selector).first
                if container.is_visible(timeout=500):
                    # Check for subscribe buttons/links within this container
                    for keyword in subscribe_keywords:
                        try:
                            # Check for button role within container
                            button = container.get_by_role("button", name=keyword, exact=False)
                            if button.count() > 0 and button.first.is_visible(timeout=500):
                                return True
                        except Exception:
                            pass
                        
                        try:
                            # Check for link role within container
                            link = container.get_by_role("link", name=keyword, exact=False)
                            if link.count() > 0 and link.first.is_visible(timeout=500):
                                return True
                        except Exception:
                            pass
            except Exception:
                continue
        
        # Check in iframes (within consent containers)
        try:
            for frame in page.frames:
                for container_selector in consent_container_selectors:
                    try:
                        container = frame.locator(container_selector).first
                        if container.is_visible(timeout=500):
                            for keyword in subscribe_keywords:
                                try:
                                    button = container.get_by_role("button", name=keyword, exact=False)
                                    if button.count() > 0 and button.first.is_visible(timeout=500):
                                        return True
                                except Exception:
                                    pass
                                
                                try:
                                    link = container.get_by_role("link", name=keyword, exact=False)
                                    if link.count() > 0 and link.first.is_visible(timeout=500):
                                        return True
                                except Exception:
                                    pass
                    except Exception:
                        continue
        except Exception:
            pass
        
        # No fallback broad search - only subscribe buttons within consent containers are relevant
        # This prevents false positives from video CTAs, newsletter signups, etc.
    except Exception:
        pass
    
    return False


def detect_essentials_only_button(page: Page, essentials_only_keywords: List[str]) -> bool:
    """
    Detect if an essentials only button is available on the page.
    """
    handler = CookieConsentHandler(accept_keywords=essentials_only_keywords)
    return handler._detect_essentials_only_button(page, essentials_only_keywords)


def accept_essentials_only(page: Page, essentials_only_keywords: List[str]) -> bool:
    """
    Attempt to accept only essential/necessary cookies.
    """
    handler = CookieConsentHandler(accept_keywords=essentials_only_keywords)
    return handler.accept_essentials_only(page, essentials_only_keywords)