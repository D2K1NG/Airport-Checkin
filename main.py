import time
import os
import requests
from playwright.sync_api import sync_playwright

# ================= 配置区域 =================
TARGET_URL = os.environ.get("URL")
# 这里接收你的原始字符串：referral=xxx; kata_t=xxx...
COOKIE_STR = os.environ.get("COOKIE") 

# 选填
USER_AGENT = os.environ.get("USER_AGENT")
TG_BOT = os.environ.get("TGBOT")
TG_USER = os.environ.get("TGUSERID")
# ===========================================

def send_tg(msg):
    if TG_BOT and TG_USER:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_BOT}/sendMessage", 
                          json={"chat_id": TG_USER, "text": msg, "parse_mode": "HTML"}, timeout=5)
        except: pass

def parse_cookie_string(raw_str):
    """
    🍪 核心功能：解析原始 Cookie 字符串
    输入: "key1=value1; key2=value2"
    输出: [{'name': 'key1', 'value': 'value1', ...}, ...]
    """
    if not raw_str:
        return []
    
    cookies = []
    # 1. 按分号拆分
    items = raw_str.split(';')
    
    for item in items:
        if '=' in item:
            # 2. 按第一个等号拆分 name 和 value
            name, value = item.strip().split('=', 1)
            cookies.append({
                'name': name,
                'value': value,
                'domain': 'dashboard.katabump.com', # 必填：硬编码适配目标网站
                'path': '/'
            })
    return cookies

def run():
    print("🚀 启动 (Raw String Cookie 版)...")
    
    if not COOKIE_STR:
        print("❌ 错误：环境变量 COOKIE 为空！")
        send_tg("❌ 失败：未设置 COOKIE Secret")
        return

    # 1. 解析 Cookie
    parsed_cookies = parse_cookie_string(COOKIE_STR)
    print(f"🍪 解析到 {len(parsed_cookies)} 个 Cookie，准备注入...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, # 必须为 False 配合 xvfb
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        
        # 2. 创建上下文并注入 Cookie
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=USER_AGENT or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        try:
            context.add_cookies(parsed_cookies)
            print("✅ Cookie 注入成功！")
        except Exception as e:
            print(f"❌ Cookie 注入失败: {e}")
            return

        page = context.new_page()
        page.set_default_timeout(45000)

        # 3. 访问页面
        print(f"👉 访问: {TARGET_URL}")
        try:
            page.goto(TARGET_URL, wait_until='domcontentloaded')
        except: pass
        
        page.wait_for_timeout(5000)

        # 4. 登录检查
        if "login" in page.url or page.locator("input[name='email']").is_visible():
            print("❌ 免登失败：依然在登录页。")
            print("💡 可能原因：提供的字符串缺少 cf_clearance (Cloudflare验证) 或 session 已过期。")
            page.screenshot(path="login_failed.png")
            send_tg("❌ 续期失败：Cookie 无效，无法跳过登录。")
            browser.close()
            return

        print("✅ 免登成功！寻找 Renew 按钮...")

        # 5. 点击 Renew
        renew_btn = None
        if page.get_by_text("Renew", exact=True).count() > 0:
             renew_btn = page.get_by_text("Renew", exact=True).first
        elif page.locator('[data-bs-target="#renew-modal"]').count() > 0:
             renew_btn = page.locator('[data-bs-target="#renew-modal"]').first
        
        if renew_btn:
            renew_btn.click()
            print("⏳ 弹窗已开，寻找验证码 Iframe...")
            time.sleep(5)

            # 6. Iframe 穿透 (Cloudflare)
            target_frame = None
            for frame in page.frames:
                if "cloudflare" in frame.url or "turnstile" in frame.url:
                    target_frame = frame
                    break
            
            if target_frame:
                print(f"✅ 锁定验证 Iframe: {target_frame.url}")
                try:
                    # 优先点 checkbox，不行点 body
                    target_frame.locator("input[type='checkbox']").click(timeout=3000)
                    print("🖱️ 点击了验证框")
                except:
                    target_frame.locator("body").click(timeout=3000)
                    print("🖱️ 点击了验证体")
                time.sleep(3)
            else:
                print("⚠️ 未找到 Iframe，尝试点击屏幕中央...")
                page.mouse.click(960, 540)

            # 7. 提交
            print("🚀 提交...")
            btn = page.locator("#renew-modal button.btn-primary")
            if btn.is_visible():
                btn.click()
            else:
                page.keyboard.press("Enter")

            time.sleep(5)
            if page.locator(".alert-success").is_visible() or "success" in page.content().lower():
                print("✅ 成功！")
                send_tg("✅ 续期成功！")
            else:
                page.screenshot(path="result.png")
                print("❓ 未检测到成功信号，请检查截图。")
        else:
            print("ℹ️ 未找到 Renew 按钮")

        browser.close()

if __name__ == "__main__":
    run()
