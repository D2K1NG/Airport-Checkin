import time
import os
import requests
from playwright.sync_api import sync_playwright

# ================= 配置 =================
TARGET_URL = os.environ.get("URL")
COOKIE_STR = os.environ.get("COOKIE") 
USER_AGENT = os.environ.get("USER_AGENT")
TG_BOT = os.environ.get("TGBOT")
TG_USER = os.environ.get("TGUSERID")
# =======================================

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

def run():
    print("🚀 启动 (FrameLocator 核心修复版)...")
    os.makedirs("videos", exist_ok=True)

    if not TARGET_URL or not COOKIE_STR:
        print("❌ 错误：变量未设置")
        return

    parsed_cookies = parse_cookie_string(COOKIE_STR)

    with sync_playwright() as p:
        # 基础启动参数，不搞花哨的
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--window-size=1920,1080'
            ]
        )
        
        # 使用指定 UA
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=USER_AGENT or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            record_video_dir="videos/",
            record_video_size={"width": 1920, "height": 1080}
        )

        try:
            context.add_cookies(parsed_cookies)
            page = context.new_page()
            
            # 最基础的 webdriver 隐藏
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page.set_default_timeout(60000)

            print(f"👉 访问: {TARGET_URL}")
            try:
                page.goto(TARGET_URL, wait_until='domcontentloaded')
            except: pass
            page.wait_for_timeout(5000)

            if "login" in page.url:
                print("❌ Cookie失效")
                return

            # --- Renew 流程 ---
            # 优先点 Renew 按钮
            renew_btn = page.locator('[data-bs-target="#renew-modal"]').first
            if not renew_btn.is_visible():
                renew_btn = page.get_by_text("Renew", exact=True).first
            
            if renew_btn.is_visible():
                print("🖱️ 点击 Renew...")
                renew_btn.click()
                
                # 显式等待弹窗出现
                print("⏳ 等待弹窗加载...")
                page.locator("#renew-modal").wait_for(state="visible", timeout=10000)
                time.sleep(3) # 给 iframe 渲染留点时间

                # =================================================
                # 👇 唯一的逻辑：使用 frame_locator 锁定 Cloudflare
                # =================================================
                print("🔍 寻找 Cloudflare 验证码...")
                
                # 1. 定义 Cloudflare iframe 的定位器 (不立即寻找，而是定义规则)
                # Cloudflare 的特征是 src 包含 challenges 或 turnstile
                cf_frame_locator = page.frame_locator("iframe[src*='challenges'], iframe[src*='turnstile']")
                
                # 2. 定位 iframe 内部的 body (或者 checkbox)
                # 使用 first 确保即使有多个也能选中第一个
                cf_body = cf_frame_locator.locator("body").first
                
                try:
                    # 3. 等待它出现 (Playwright 会自动 retry)
                    cf_body.wait_for(timeout=15000)
                    print("✅ 找到验证码框架！")
                    
                    # 4. 获取它的空间坐标 (Bounding Box)
                    # 注意：我们获取的是 iframe 内部 body 的坐标，或者 iframe 元素本身的坐标
                    # 为了稳妥，我们退回到获取 iframe 元素本身
                    iframe_element = page.locator("iframe[src*='challenges'], iframe[src*='turnstile']").first
                    box = iframe_element.bounding_box()
                    
                    if box:
                        # 计算中心点
                        click_x = box['x'] + 30 # 靠左一点，通常是 checkbox 的位置
                        click_y = box['y'] + (box['height'] / 2)
                        
                        print(f"🎯 鼠标移动到: {click_x}, {click_y}")
                        page.mouse.move(click_x, click_y)
                        time.sleep(0.5)
                        
                        print("🖱️ 物理点击！")
                        page.mouse.down()
                        time.sleep(0.2) # 模拟按压耗时
                        page.mouse.up()
                        
                        print("⏳ 点击完成，等待8秒让验证通过...")
                        time.sleep(8)
                    else:
                        print("❌ 无法获取坐标，跳过点击")

                except Exception as e:
                    print(f"❌ 没找到验证码 (超时): {e}")
                    # 如果真的没找到，这里什么都不做，绝不盲点屏幕防止误关弹窗

                # =================================================

                # 提交
                print("🚀 提交...")
                submit_btn = page.locator("#renew-modal button.btn-primary")
                if submit_btn.is_visible():
                    submit_btn.click()
                else:
                    page.keyboard.press("Enter")

                time.sleep(5)
                
                if page.locator(".alert-success").is_visible():
                    print("✅✅✅ 成功！")
                    send_tg("✅ 续期成功")
                else:
                    print("❓ 未检测到成功提示")
                    page.screenshot(path="result.png")

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
