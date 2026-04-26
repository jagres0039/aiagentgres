
from playwright.sync_api import sync_playwright
import time
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080}, storage_state='/root/aiagent/playwright_cookies.json', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0')
        page = context.new_page()
        page.goto('https://x.com/okx/status/2039817926795018675?s=20', timeout=60000, wait_until='domcontentloaded')
        time.sleep(8)
        
        # --- PROSES 1: LIKE ---
        print("🔍 Mengeksekusi Like...")
        like_btn = page.locator('[data-testid="like"]').first
        unlike_btn = page.locator('[data-testid="unlike"]').first
        
        if unlike_btn.is_visible():
            print("✅ LIKE: Udah di-Like sebelumnya bro! ❤️")
        elif like_btn.is_visible():
            like_btn.click(force=True)
            time.sleep(2)
            print("✅ LIKE: SUKSES nge-Like! ❤️")
        else:
            print("❌ LIKE: GAGAL, tombol Like ga ketemu.")
            
        time.sleep(2) # Jeda nafas bentar
        
        # --- PROSES 2: RETWEET ---
        print("🔍 Mengeksekusi Retweet...")
        unretweet_btn = page.locator('[data-testid="unretweet"]').first
        retweet_btn = page.locator('[data-testid="retweet"]').first
        
        if unretweet_btn.is_visible():
            print("✅ RETWEET: Udah di-Repost sebelumnya bro! ♻️")
        elif retweet_btn.is_visible():
            retweet_btn.click(force=True)
            time.sleep(2) 
            confirm_btn = page.locator('[data-testid="retweetConfirm"]').first
            if confirm_btn.is_visible():
                confirm_btn.click(force=True)
                time.sleep(4)
                print("✅ RETWEET: SUKSES nge-Repost! ♻️")
            else:
                print("❌ RETWEET: GAGAL, tombol popup Repost ga ketemu.")
        else:
            print("❌ RETWEET: GAGAL, tombol panah Retweet ga ketemu.")
            
        browser.close()
except Exception as e:
    print(f"❌ CRASH: {str(e)}")
