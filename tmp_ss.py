
from playwright.sync_api import sync_playwright
import time
import os

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, 
            args=[
                '--no-sandbox', 
                '--disable-setuid-sandbox', 
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled'
            ]
        )
        
        cookie_file = '/root/aiagent/playwright_cookies.json'
        ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        
        # BIKIN SIMPEL: Kalau file cookies ada, sikat langsung pake!
        if os.path.exists(cookie_file):
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080}, 
                device_scale_factor=2,
                storage_state=cookie_file,
                user_agent=ua
            )
        else:
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080}, 
                device_scale_factor=2,
                user_agent=ua
            )
            
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        page.goto('https://www.vivo.com/id/products/t2x', timeout=60000)
        time.sleep(10)  # Nunggu 10 detik biar tweetnya ke-load semua
        
        page.screenshot(path='/root/aiagent/outputs/ss.png', full_page=False)
        browser.close()
except Exception as e:
    print("ERROR:", e)
