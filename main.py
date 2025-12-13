import time
import os
import sys
import shutil
import requests
from playwright.sync_api import sync_playwright

# ==========================================
# 👇 环境变量配置 👇
# ==========================================
URL = os.environ.get("URL") 
GMAIL = os.environ.get("GMAIL")
KATAMIMA = os.environ.get("KATAMIMA")
COOKIE_STR = os.environ.get("COOKIE")
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_USER_ID = os.environ.get("TG_USER_ID")

VIDEO_DIR = "videos"

# ==========================================
# 👇 工具函数 👇
# ==========================================

def send_telegram(msg):
    """发送 Telegram 通知"""
    print(f"🔔 TG通知: {msg}")
    if not TG_TOKEN or not TG_USER_ID: return
    
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_USER_ID,
        "text": f"🤖 **VPS 续期助手 (V39)**\n\n{msg}",
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"⚠️ TG 发送失败: {e}")

def parse_cookie_str(cookie_str, domain):
    cookies = []
    if not cookie_str: return cookies
    try:
        for item in cookie_str.split(';'):
            if '=' in item:
                name, value = item.strip().split('=', 1)
                cookies.append({
                    'name': name.strip(),
                    'value': value.strip(),
                    'domain': domain,
                    'path': '/'
                })
    except Exception as e:
        print(f"⚠️ Cookie 解析失败: {e}")
    return cookies

# ==========================================
# 👇 主逻辑 👇
# ==========================================

def run():
    print("🚀 启动 V39 (登录页兜底策略)...")

    if not URL:
        print("❌ 错误：未检测到 URL 环境变量！")
        sys.exit(1)
    if not GMAIL or not KATAMIMA:
        print("❌ 错误：缺少 GMAIL 或 KATAMIMA 环境变量")
        sys.exit(1)

    # 清理旧视频
    if os.path.exists(VIDEO_DIR):
        shutil.rmtree(VIDEO_DIR)
    os.makedirs(VIDEO_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )

        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale='zh-CN',
            record_video_dir=VIDEO_DIR,
            record_video_size={"width": 1920, "height": 1080}
        )

        # 1. 尝试注入 Cookie
        try:
            domain = URL.split("/")[2]
        except:
            domain = "dashboard.katabump.com"

        if COOKIE_STR:
            print("🍪 注入 Secret 中的 Cookie...")
            context.add_cookies(parse_cookie_str(COOKIE_STR, domain))
        
        page = context.new_page()
        page.set_default_timeout(60000)

        # --- 🛡️ V39 核心：智能导航策略 ---
        print(f"👉 尝试访问目标页面 (URL 已隐藏)")
        try:
            page.goto(URL, wait_until='domcontentloaded')
        except Exception as e:
            # 只要访问目标页报错 (无论是重定向死循环，还是 chromewebdata 错误)
            # 我们就放弃目标页，改去登录页！
            print(f"⚠️ 访问目标页失败 ({str(e)})")
            print("🛡️ 策略切换：Cookie 已失效且硬闯失败，转为【直连登录页】...")
            
            # 1. 彻底清除旧 Cookie
            context.clear_cookies()
            
            # 2. 显式前往登录页 (不再去碰那个报错的 URL)
            login_url = "https://dashboard.katabump.com/auth/login"
            print(f"👉 前往登录页: {login_url}")
            
            try:
                page.goto(login_url, wait_until='domcontentloaded')
            except Exception as login_e:
                msg = f"❌ 连登录页都打不开，网站可能挂了: {login_e}"
                print(msg)
                send_telegram(msg)
                sys.exit(1)
        
        page.wait_for_timeout(3000)

        # 2. 统一登录处理
        # 此时页面可能是目标页 (Cookie有效)，也可能是登录页 (Cookie失效后跳转过来的)
        is_login_page = "login" in page.url or page.locator("#email").is_visible()
        
        if is_login_page:
            print("🛑 当前在登录页，执行密码登录...")
            # 再次确保环境干净
            context.clear_cookies() 
            
            try:
                page.fill("#email", GMAIL)
                page.fill("#password", KATAMIMA)
                if page.locator("#rememberMe").is_visible():
                    page.check("#rememberMe")
                
                print("👆 点击登录...")
                page.click("#submit")
                
                # 等待跳转
                page.wait_for_url(lambda u: "login" not in u, timeout=40000)
                print("✅ 密码登录成功！")
                
                # 登录成功后，才再次尝试去目标页面
                if "servers/edit" not in page.url:
                    print(f"👉 登录完成，跳转回目标 URL...")
                    page.goto(URL)
                    page.wait_for_timeout(5000)
                    
            except Exception as e:
                err = f"❌ 登录过程失败: {str(e)}"
                print(err)
                send_telegram(err)
                page.screenshot(path="login_error.png")
                context.close(); browser.close(); sys.exit(1)
        else:
            print("✅ 直接进入了后台，无需登录！")

        # 3. Renew 流程
        print("🤖 寻找 Renew 按钮...")
        page.wait_for_timeout(3000)
        
        renew_found = False
        try:
            if page.locator('[data-bs-target="#renew-modal"]').is_visible():
                page.locator('[data-bs-target="#renew-modal"]').click()
                renew_found = True
            elif page.get_by_text("Renew", exact=True).count() > 0:
                page.get_by_text("Renew", exact=True).first.click()
                renew_found = True
        except:
            pass

        if not renew_found:
            print("⚠️ 未找到 Renew 按钮，可能页面已变动或无需续期。")
            page.screenshot(path="debug_no_renew.png")

        print("⏳ 弹窗触发，等待 10 秒加载验证码 iframe...")
        time.sleep(10)

        # 4. 解决验证码 (iframe 优先)
        print("⚡ 开始验证 (寻找 Cloudflare iframe)...")
        try:
            # 寻找包含 challenges 的 iframe
            cf_frame = page.frame_locator("iframe[src*='challenges']").first
            # 等待 iframe 里的 body 出现
            if cf_frame.locator("body").is_visible():
                print("🖱️ 找到验证码 iframe，点击其中心区域...")
                # 强制点击 iframe 里的 body
                cf_frame.locator("body").click(force=True, timeout=5000)
                time.sleep(2)
                # 再点一下 checkbox (如果有具体的 id 更好，但 body 通常能触发)
                try:
                    cf_frame.locator("input[type='checkbox']").click(force=True, timeout=2000)
                except:
                    pass
            else:
                raise Exception("iframe body not visible")
        except Exception as e:
            print(f"⚠️ iframe 点击失败，尝试备用方案 (坐标点击)...")
            try:
                ref_text = page.locator("#renew-modal").get_by_text("Captcha", exact=True).first
                if not ref_text.is_visible():
                    ref_text = page.locator("#renew-modal").get_by_text("This will extend", exact=False).first
                
                if ref_text.is_visible():
                    box = ref_text.bounding_box()
                    if box:
                        target_x = box['x'] + 25
                        target_y = box['y'] + 60
                        print(f"📍 坐标点击: {target_x}, {target_y}")
                        page.mouse.move(target_x, target_y)
                        time.sleep(0.5)
                        page.mouse.click(target_x, target_y)
            except:
                pass

        print("⏳ 等待 5 秒验证生效...")
        time.sleep(5)

        # 5. 提交
        print("🚀 提交 Renew...")
        try:
            renew_submit = page.locator("#renew-modal button.btn-primary", has_text="Renew")
            # 检查是否可点击
            if renew_submit.is_visible():
                renew_submit.click(force=True)
            else:
                page.keyboard.press("Enter")
        except:
            pass

        print("⏳ 等待结果...")
        time.sleep(5)
        
        # 6. 结果判定
        page.screenshot(path="result.png")
        
        msg = ""
        if page.locator("div.alert-success").is_visible():
            msg = "✅ **续期成功 (Success)**"
        elif page.get_by_text("You can't renew your server yet").is_visible():
            msg = "🕒 **未到时间 (Too Early)**\n登录正常，但还没到续期时间。"
        elif page.get_by_text("Please complete the captcha").is_visible():
            msg = "❌ **验证码失败 (Captcha Fail)**"
        elif page.locator("div.alert-danger").is_visible():
            msg = "❌ **网站报错 (Error)**"
        else:
            msg = "❓ **状态未知 (Unknown)**\n请查看录屏。"

        print(msg)
        send_telegram(msg)
        
        context.close()
        print(f"📹 录屏已保存至 {VIDEO_DIR}/")
        browser.close()

if __name__ == "__main__":
    run()
