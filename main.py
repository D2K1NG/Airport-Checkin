import time
import random
import os
import requests
from playwright.sync_api import sync_playwright

#Env
TARGET_URL = os.environ.get("URL")
COOKIE_STR = os.environ.get("COOKIE") 
USER_AGENT = os.environ.get("USER_AGENT")
TG_BOT = os.environ.get("TGBOT")
TG_USER = os.environ.get("TGUSERID")

def send_tg(msg):
    if TG_BOT and TG_USER:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_BOT}/sendMessage", 
                          json={"chat_id": TG_USER, "text": msg, "parse_mode": "HTML"}, timeout=5)
        except: pass

def parse_cookie_string(raw_str):
    if not raw_str: return []
    cookies = []
    items = raw_str.split(';')
    for item in items:
        if '=' in item:
            try:
                name, value = item.strip().split('=', 1)
                cookies.append({
                    'name': name, 'value': value,
                    'domain': 'dashboard.katabump.com', 'path': '/'
                })
            except: continue
    return cookies

def apply_stealth(page):
    """最基础的特征去除，防止一打开就被ban"""
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    page.add_init_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")

def run():
    print("🚀 启动 (坐标暴力点击版)...")
    os.makedirs("videos", exist_ok=True)

    if not TARGET_URL or not COOKIE_STR:
        print("❌ 错误：变量未设置")
        return

    parsed_cookies = parse_cookie_string(COOKIE_STR)

    with sync_playwright() as p:
        # 启动参数
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--window-size=1920,1080'
            ]
        )
        
        # 使用真实 Windows UA
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=USER_AGENT or ua,
            record_video_dir="videos/",
            record_video_size={"width": 1920, "height": 1080}
        )

        try:
            context.add_cookies(parsed_cookies)
            page = context.new_page()
            apply_stealth(page)
            page.set_default_timeout(60000)

            print(f"👉 访问: {TARGET_URL}")
            try:
                page.goto(TARGET_URL, wait_until='domcontentloaded')
            except: pass
            page.wait_for_timeout(5000)

            if "login" in page.url:
                print("❌ Cookie失效")
                page.screenshot(path="login_fail.png")
                return

            # --- Renew ---
            renew_btn = None
            if page.get_by_text("Renew", exact=True).count() > 0:
                 renew_btn = page.get_by_text("Renew", exact=True).first
            elif page.locator('[data-bs-target="#renew-modal"]').count() > 0:
                 renew_btn = page.locator('[data-bs-target="#renew-modal"]').first
            
            if renew_btn:
                print("🖱️ 点击 Renew...")
                renew_btn.click()
                
                print("⏳ 等待弹窗和验证码加载 (10秒)...")
                time.sleep(10)

                # ==========================================
                # 👇 核心：寻找 Iframe 并计算坐标点击
                # ==========================================
                
                print("🔍 正在定位 Cloudflare Iframe...")
                
                # 1. 寻找页面中所有 iframe
                target_frame_element = None
                
                # Cloudflare 的 iframe 域名通常包含 challenges 或 turnstile
                # 我们通过定位器找到这个 iframe 元素
                cf_iframe_locator = page.locator("iframe[src*='challenges'], iframe[src*='turnstile']")
                
                if cf_iframe_locator.count() > 0:
                    target_frame_element = cf_iframe_locator.first
                    print("✅ 找到了验证码 Iframe！")
                else:
                    print("⚠️ 没找到特定 iframe，尝试寻找所有 iframe...")
                    frames = page.locator("iframe")
                    if frames.count() > 0:
                        target_frame_element = frames.first
                
                # 2. 如果找到了，计算它的坐标
                if target_frame_element:
                    # 获取 iframe 在屏幕上的位置 (x, y, width, height)
                    box = target_frame_element.bounding_box()
                    
                    if box:
                        center_x = box['x'] + (box['width'] / 2)
                        # Cloudflare 的 checkbox 通常在 iframe 垂直居中偏左一点，或者正中间
                        # 我们稍微加一点随机偏移，防止太死板
                        center_y = box['y'] + (box['height'] / 2)
                        
                        print(f"🎯 锁定坐标: X={center_x}, Y={center_y}")
                        
                        # 3. 移动鼠标过去
                        print("🖱️ 鼠标移动过去...")
                        page.mouse.move(center_x, center_y, steps=20) # steps=20 让移动有轨迹，不是瞬移
                        time.sleep(0.5)
                        
                        # 4. 物理点击
                        print("🖱️ 点击！")
                        page.mouse.down()
                        time.sleep(random.uniform(0.1, 0.3)) # 按住一会
                        page.mouse.up()
                        
                        print("⏳ 点击完成，等待验证变绿 (8秒)...")
                        time.sleep(8)
                    else:
                        print("❌ 无法获取 Iframe 坐标")
                else:
                    print("❌ 根本没找到 Iframe 元素，无法点击")
                    # 只有在这里我们才尝试盲点屏幕中间，作为最后的挣扎
                    page.mouse.click(960, 500)

                # ==========================================

                # 提交
                print("🚀 提交 Renew...")
                btn = page.locator("#renew-modal button.btn-primary")
                if btn.is_visible():
                    btn.click()
                else:
                    page.keyboard.press("Enter")

                time.sleep(5)
                
                if page.locator(".alert-success").is_visible():
                    print("✅✅✅ 成功！")
                    send_tg("✅ 续期成功！")
                elif page.get_by_text("Please complete the captcha").is_visible():
                    print("❌ 失败：验证码没点中，或被拦截")
                    send_tg("❌ 失败：验证码问题")
                    page.screenshot(path="captcha_fail.png")
                else:
                    print("❓ 未知结果")
                    page.screenshot(path="unknown.png")

            else:
                print("ℹ️ 未找到 Renew 按钮")

        except Exception as e:
            print(f"❌ 错误: {e}")
        finally:
            print("💾 保存录像...")
            try:
                context.close()
                browser.close()
            except: pass

if __name__ == "__main__":
    run()
