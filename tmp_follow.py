
from playwright.sync_api import sync_playwright
import time
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080}, storage_state='/root/aiagent/playwright_cookies.json', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0')
        page = context.new_page()
        page.goto('https://x.com/WatcherGuru', timeout=60000, wait_until='domcontentloaded')
        time.sleep(8)
        
        print("🔍 Mencari tombol Follow...")
        # Trik nangkep tombol follow Twitter yang ID-nya dinamis
        unfollow_btn = page.locator('button[data-testid$="-unfollow"]').first
        follow_btn = page.locator('button[data-testid$="-follow"]').first
        
        if unfollow_btn.is_visible():
            print("✅ Udah lu Follow sebelumnya bro! 🤝")
        elif follow_btn.is_visible():
            follow_btn.click(force=True)
            time.sleep(3)
            print("✅ SUKSES: Berhasil nge-Follow! 👤+")
        else:
            # Backup plan kalau tombol utama disembunyiin
            alt_follow = page.locator('button[role="button"]:has-text("Follow")').first
            if alt_follow.is_visible():
                alt_follow.click(force=True)
                time.sleep(3)
                print("✅ SUKSES: Berhasil nge-Follow (Alternatif)! 👤+")
            else:
                print("❌ GAGAL: Tombol Follow ga ketemu.")
                
        browser.close()
except Exception as e:
    print(f"❌ CRASH: {str(e)}")
