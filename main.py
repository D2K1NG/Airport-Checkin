import time
import os
import sys
import shutil
import requests
from playwright.sync_api import sync_playwright

# ==========================================
# 👇 环境变量配置 (V38 容错版) 👇
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
        "text": f"🤖 **VPS 续期助手 (V38)**\n\n{msg}",
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
    print("🚀 启动 V38 (增加重定向自动修复功能)...")

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
            cookies = parse_cookie_str(COOKIE_STR, domain)
            context.add_cookies(cookies)
        
        page = context.new_page()
        page.set_default_timeout(60000)

        # --- 🛡️ 核心修复：稳健导航模块 ---
        print(f"👉 前往目标页面 (URL 已隐藏)")
        try:
            page.goto(URL, wait_until='domcontentloaded')
        except Exception as e:
            error_str = str(e)
            # 捕获 "重定向过多" 错误
            if "ERR_TOO_MANY_REDIRECTS" in error_str:
                print(f"⚠️ 捕获重定向死循环，说明 Cookie 已失效！")
                print("🧹 正在清除 Cookie 并重试...")
                
                # 关键步骤：清除烂掉的 Cookie
                context.clear_cookies()
                
                # 重新尝试访问（这次应该会正常跳转到登录页，而不会死循环）
                try:
                    page.goto(URL, wait_until='domcontentloaded')
                    print("🔄 重试导航成功！")
                except Exception as retry_e:
                    msg = f"❌ 重试依然失败: {retry_e}"
                    print(msg)
                    send_telegram(msg)
                    sys.exit(1)
            else:
                # 其他错误（如断网）直接抛出
                raise e
        
        page.wait_for_timeout(5000)

        # 2. 检查登录状态
        is_login_page = "login" in page.url or page.locator("#email").is_visible()
        
        if is_login_page:
            print("🛑 需要登录，切换至密码模式...")
            context.clear_cookies() #以此确保环境干净
            
            try:
                page.fill("#email", GMAIL)
                page.fill("#password", KATAMIMA)
                if page.locator("#rememberMe").is_visible():
                    page.check("#rememberMe")
                
                print("👆 点击登录...")
                page.click("#submit")
                
                # 等待跳转，容错时间加长
                page.wait_for_url(lambda u: "login" not in u, timeout=40000)
                print("✅ 密码登录成功！")
                
                if "servers/edit" not in page.url:
                    page.goto(URL)
                    page.wait_for_timeout(5000)
                    
            except Exception as e:
                err = f"❌ 登录失败: {str(e)}"
                print(err)
                send_telegram(err)
                page.screenshot(path="login_error.png")
                context.close(); browser.close(); sys.exit(1)
        else:
            print("✅ Cookie 有效，直接进入后台！")

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
            cf_frame = page.frame_locator("iframe[src*='challenges']").first
            if cf_frame.locator("body").is_visible():
                print("🖱️ 找到验证码 iframe，点击中心...")
                cf_frame.locator("body").click(timeout=5000)
                time.sleep(5)
            else:
                raise Exception("iframe not visible")
        except Exception as e:
            print(f"⚠️ iframe 点击失败，切换到坐标打击...")
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
            if renew_submit.is_enabled():
                renew_submit.click()
            else:
                renew_submit.click(force=True)
        except:
            page.keyboard.press("Enter")

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
