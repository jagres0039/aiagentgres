
from playwright.sync_api import sync_playwright
import time
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080}, storage_state='/root/aiagent/playwright_cookies.json', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0')
        page = context.new_page()
        page.goto('https://x.com/Airdropfinds/status/2040088685148835893?s=20', timeout=60000, wait_until='domcontentloaded')
        time.sleep(8)
        
        print("🔍 Mencari kotak komentar inline...")
        # Kalo lu buka link tweet, kotak komen biasanya langsung ada di bawahnya
        textbox = page.locator('[data-testid="tweetTextarea_0"]').first
        if textbox.is_visible():
            textbox.click(force=True)
            time.sleep(1)
            page.keyboard.type('''menyerah bang''', delay=50)
            time.sleep(2)
            
            print("🔍 Mencari tombol Reply...")
            reply_btn = page.locator('[data-testid="tweetButtonInline"]').first
            if not reply_btn.is_visible():
                reply_btn = page.locator('[data-testid="tweetButton"]').first
                
            if reply_btn.is_visible():
                reply_btn.click(force=True)
                time.sleep(6)
                print("✅ SUKSES: Komentar berhasil meluncur! 💬")
            else:
                print("❌ GAGAL: Tombol Reply ga ketemu / masih abu-abu.")
        else:
            print("❌ GAGAL: Kotak komentar ga ketemu di halaman ini.")
            
        page.screenshot(path='/root/aiagent/outputs/ss_reply.png')
        browser.close()
except Exception as e:
    print(f"❌ CRASH: {str(e)}")
