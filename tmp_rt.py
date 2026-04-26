
from playwright.sync_api import sync_playwright
import time
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080}, storage_state='/root/aiagent/playwright_cookies.json', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0')
        page = context.new_page()
        page.goto('https://x.com/i/status/2041084180998562114', timeout=60000, wait_until='domcontentloaded')
        time.sleep(8)
        
        print("🔍 Mencari tombol Retweet...")
        unretweet_btn = page.locator('[data-testid="unretweet"]').first
        retweet_btn = page.locator('[data-testid="retweet"]').first
        
        if unretweet_btn.is_visible():
            print("✅ Udah di-Repost sebelumnya bro! ♻️")
        elif retweet_btn.is_visible():
            retweet_btn.click(force=True)
            time.sleep(2) 
            
            print("🔍 Mencari konfirmasi Repost...")
            confirm_btn = page.locator('[data-testid="retweetConfirm"]').first
            if confirm_btn.is_visible():
                confirm_btn.click(force=True)
                time.sleep(5)
                print("✅ SUKSES: Berhasil nge-Repost bang! ♻️")
            else:
                print("❌ GAGAL: Tombol popup Repost ga ketemu bang.")
        else:
            print("❌ GAGAL: Tombol panah Retweet ga ketemu bang.")
            
        browser.close()
except Exception as e:
    print(f"❌ CRASH: {str(e)}")
