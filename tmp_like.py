
from playwright.sync_api import sync_playwright
import time
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080}, storage_state='/root/aiagent/playwright_cookies.json', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0')
        page = context.new_page()
        page.goto('https://x.com/Airdropfinds/status/2040088685148835893?s=20', timeout=60000, wait_until='domcontentloaded')
        time.sleep(8)
        
        print("🔍 Mencari tombol Like...")
        like_btn = page.locator('[data-testid="like"]').first
        unlike_btn = page.locator('[data-testid="unlike"]').first
        
        if unlike_btn.is_visible():
            print("✅ Udah di-Like sebelumnya bro! ❤️")
        elif like_btn.is_visible():
            like_btn.click(force=True)
            time.sleep(3)
            print("✅ SUKSES: Berhasil di Like ngab! ❤️")
        else:
            print("❌ GAGAL: Tombol Like ga ketemu bang.")
            
        browser.close()
except Exception as e:
    print(f"❌ CRASH: {str(e)}")
