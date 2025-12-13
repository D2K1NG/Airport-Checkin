import time
import os
import requests
from playwright.sync_api import sync_playwright

# ================= 配置区域 =================
# 1. 目标网址: https://dashboard.katabump.com/servers/edit?id=180484
TARGET_URL = os.environ.get("URL")

# 2. Cookie 字符串: referral=...; katabump_s=...
COOKIE_STR = os.environ.get("COOKIE") 

# 3. 选填配置
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
    🍪 解析原始字符串格式的 Cookie
    """
    if not raw_str:
        return []
    
    cookies = []
    items = raw_str.split(';')
    for item in items:
        if '=' in item:
            try:
                name, value = item.strip().split('=', 1)
                cookies.append({
                    'name': name,
                    'value': value,
                    'domain': 'dashboard.katabump.com', # 强制指定域名
                    'path': '/'
                })
            except:
                continue
    return cookies

def run():
    print("🚀 启动 Katabump 自动续期...")
    
    if not TARGET_URL:
        print("❌ 错误：未设置 URL 变量")
        return

    if not COOKIE_STR:
        print("❌ 错误：未设置 COOKIE 变量")
        return

    # 1. 解析 Cookie
    parsed_cookies = parse_cookie_string(COOKIE_STR)
    print(f"🍪 已解析 {len(parsed_cookies)} 个 Cookie，准备注入...")

    with sync_playwright() as p:
        # 启动浏览器 (有头模式，配合xvfb)
        browser = p.chromium.launch(
            headless=False, 
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
        page.set_default_timeout(60000)

        # 3. 访问页面
        print(f"👉 访问: {TARGET_URL}")
        try:
            page.goto(TARGET_URL, wait_until='domcontentloaded')
        except: pass
        
        page.wait_for_timeout(5000)

        # 4. 登录检查
        # 如果 Cookie 无效，通常会跳转到 /login
        if "login" in page.url or page.locator("input[name='email']").is_visible():
            print("❌ 免登失败：页面跳转到了登录页。")
            print("💡 可能原因：Cookie 已过期 (katabump_s 失效)。")
            page.screenshot(path="login_failed.png")
            send_tg("❌ 续期失败：Cookie 无效，无法进入面板。")
            browser.close()
            return

        print("✅ 免登成功！已进入面板。")

        # 5. 寻找 Renew 按钮
        renew_btn = None
        # 尝试精确匹配 "Renew" 文本
        if page.get_by_text("Renew", exact=True).count() > 0:
             renew_btn = page.get_by_text("Renew", exact=True).first
        elif page.locator('[data-bs-target="#renew-modal"]').count() > 0:
             renew_btn = page.locator('[data-bs-target="#renew-modal"]').first
        
        if renew_btn:
            print("🖱️ 点击 Renew 按钮...")
            renew_btn.click()
            print("⏳ 弹窗已打开，等待 Cloudflare 验证码加载...")
            time.sleep(8) # 这里的等待很重要，让 iframe 加载出来

            # 6. Iframe 穿透 (处理 Renew 弹窗里的 Cloudflare)
            target_frame = None
            for frame in page.frames:
                # 寻找包含 cloudflare 或 turnstile 的 iframe
                if "cloudflare" in frame.url or "turnstile" in frame.url:
                    target_frame = frame
                    break
            
            if target_frame:
                print(f"✅ 锁定验证 Iframe: {target_frame.url}")
                try:
                    # 尝试点击 Checkbox
                    target_frame.locator("input[type='checkbox']").click(timeout=5000)
                    print("🖱️ 点击了验证框 (Checkbox)")
                except:
                    # 备选：点击 Body
                    target_frame.locator("body").click(timeout=5000)
                    print("🖱️ 点击了验证体 (Body)")
                
                # 等待验证通过
                time.sleep(5)
            else:
                print("⚠️ 未找到验证 Iframe，尝试盲点屏幕中央...")
                page.mouse.click(960, 540)
                time.sleep(2)

            # 7. 提交续期
            print("🚀 提交 Renew...")
            btn = page.locator("#renew-modal button.btn-primary")
            if btn.is_visible():
                btn.click()
            else:
                page.keyboard.press("Enter")

            time.sleep(5)
            
            # 8. 结果判定
            if page.locator(".alert-success").is_visible() or "success" in page.content().lower():
                print("✅✅✅ 续期成功！")
                send_tg("✅ Katabump 续期成功！")
            else:
                # 截图查看结果
                page.screenshot(path="result.png")
                print("❓ 流程结束，未检测到成功提示，请查看截图 result.png。")
        else:
            print("ℹ️ 未找到 Renew 按钮 (可能无需续期)。")

        browser.close()

if __name__ == "__main__":
    run()
