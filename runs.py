'''
Author: Najeh Halawani
-----
Last Modified: Tuesday, 28th October 2025 8:22:13 pm
Modified By: Najeh Halawani
-----
'''
import playwright
from playwright.sync_api import sync_playwright, Playwright

def run_accept():
    chromium = playwright.chromium
    browser = chromium.launch(headless=True)
    context = browser.new_context(
        locale='en-EN',
        # geolocation={'longitude': 12.492507, 'latitude': 41.889938 },
        # permissions=['geolocation'],
        record_har_path="har.json",
        # record_video_dir="videos/"
    )
    page = context.new_page()

    
    context.close()
    browser.close()
    
def run_reject():
    chromium = playwright.chromium
    browser = chromium.launch(headless=True)
    context = browser.new_context(
        locale='en-EN',
        # geolocation={'longitude': 12.492507, 'latitude': 41.889938 },
        # permissions=['geolocation'],
        record_har_path="har.json",
        # record_video_dir="videos/"
    )
    page = context.new_page()

    
    context.close()
    browser.close()
    
    
def run_block():
    chromium = playwright.chromium
    browser = chromium.launch(headless=True)
    context = browser.new_context(
        locale='en-EN',
        # geolocation={'longitude': 12.492507, 'latitude': 41.889938 },
        # permissions=['geolocation'],
        record_har_path="har.json",
        # record_video_dir="videos/"
    )
    page = context.new_page()

    
    context.close()
    browser.close()