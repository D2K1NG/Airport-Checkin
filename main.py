import os
import time
import requests
from playwright.sync_api import sync_playwright

# --- 环境变量 ---
COOKIE_STR = os.environ.get("COOKIE")
TARGET_URL = os.environ.get("URL") 
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_USER_ID = os.environ.get("TG_USER_ID")
USER_AGENT = os.environ.get("USER_AGENT")

def send_telegram(msg):
    print(f"🔔 TG通知: {msg}")
    if not TG_TOKEN or not TG_USER_ID: return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_USER_ID, 
        "text": f"🤖 VPS续期通知 (V24-VideoRec):\n{msg}", 
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def parse_cookies(cookie_str, domain):
    cookies = []
    if not cookie_str: return cookies
    for item in cookie_str.split(';'):
        if '=' in item:
            name, value = item.strip().split('=', 1)
            cookies.append({
                'name': name.strip(), 
                'value': value.strip(), 
                'domain': domain, 
                'path': '/'
            })
    return cookies

def run():
    print("🚀 启动 V24 全程录屏版...")
    
    if not COOKIE_STR or not TARGET_URL:
        send_telegram("❌ 致命错误：Secrets 变量缺失")
        exit(1)

    final_ua = USER_AGENT if USER_AGENT else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    
    try:
        domain = TARGET_URL.split("/")[2]
    except:
        domain = "dashboard.katabump.com"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-setuid-sandbox']
        )
        
        # --- 开启录屏的关键修改 ---
        # videos/ 是保存视频的文件夹名称
        context = browser.new_context(
            user_agent=final_ua, 
            viewport={'width': 1920, 'height': 1080}, 
            locale='zh-CN',
            record_video_dir="videos/", 
            record_video_size={"width": 1920, "height": 1080}
        )
        
        context.add_cookies(parse_cookies(COOKIE_STR, domain))
        page = context.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page.set_default_timeout(60000)

        try:
            print(f"1️⃣ 进入页面: {TARGET_URL}")
            page.goto(TARGET_URL, wait_until='domcontentloaded')
            page.wait_for_timeout(5000)

            print("2️⃣ 尝试打开 Renew 弹窗...")
            try:
                if page.locator('[data-bs-target="#renew-modal"]').is_visible():
                    page.locator('[data-bs-target="#renew-modal"]').click()
                else:
                    page.get_by_text("Renew", exact=True).first.click()
            except Exception as e:
                print(f"⚠️ 触发弹窗时遇到小问题: {e}")
            
            print("⏳ 等待 6 秒加载 Cloudflare...")
            time.sleep(6)
            
            modal = page.locator("#renew-modal")
            
            # --- Cloudflare 验证 ---
            print("🤖 寻找验证框...")
            iframe_selectors = ["iframe[src*='challenges']", "iframe[src*='turnstile']", "iframe[title*='Widget']"]
            cf_frame = None
            for selector in iframe_selectors:
                if page.locator(selector).first.is_visible():
                    cf_frame = page.frame_locator(selector).first
                    break
            
            if cf_frame:
                try:
                    print("👉 尝试点击验证框...")
                    cf_frame.locator("body").click(timeout=3000)
                    time.sleep(1)
                    box = cf_frame.locator("body").bounding_box()
                    if box:
                        page.mouse.click(box['x'] + 30, box['y'] + 30)
                    else:
                        cf_frame.locator("label").click(timeout=3000)
                except Exception as e:
                    print(f"⚠️ 点击异常: {e}")
            
            print("⏳ 等待 8 秒验证...")
            time.sleep(8)

            # --- 提交 ---
            print("🚀 提交 Renew...")
            try:
                renew_btn = modal.locator("button.btn-primary", has_text="Renew")
                if renew_btn.is_visible():
                    renew_btn.click()
                else:
                    modal.locator("button[type='submit']").click()
            except:
                page.keyboard.press("Enter")

            print("⏳ 等待结果...")
            time.sleep(5)
            
            # --- 结果判定 ---
            if page.locator("div.alert-success").is_visible() or page.get_by_text("Your service has been renewed").is_visible():
                msg = "✅ 续期成功！"
            elif page.locator(".alert-danger").is_visible():
                msg = "❌ 失败：网站报错。"
            elif modal.is_visible():
                msg = "⚠️ 警告：弹窗未关闭。"
            else:
                msg = "❓ 状态未知。"

            print(msg)
            send_telegram(msg)

        except Exception as e:
            err = f"❌ 运行崩溃: {str(e)}"
            print(err)
            send_telegram(err)
        finally:
            # --- 关键：先关闭 context 才能保存视频 ---
            context.close() 
            browser.close()

if __name__ == "__main__":
    run()
