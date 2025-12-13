import time
import os
import json
import requests
from playwright.sync_api import sync_playwright

#Env
TARGET_URL = os.environ.get("URL")
COOKIE_JSON = os.environ.get("COOKIE")
USER_AGENT = os.environ.get("USER_AGENT")
TG_BOT = os.environ.get("TGBOT")
TG_USER = os.environ.get("TGUSERID")
AUTH_FILE = "auth.json"

def send_tg(msg):
    if TG_BOT and TG_USER:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_BOT}/sendMessage", 
                          json={"chat_id": TG_USER, "text": msg, "parse_mode": "HTML"}, timeout=5)
        except: pass

def setup_auth_file():
    """
    直接将 Secret 内容写入 auth.json，让 Playwright 原生加载。
    完美兼容 {"cookies": [], "origins": []} 格式。
    """
    if not COOKIE_JSON:
        print("❌ 错误：未检测到 COOKIE 环境变量")
        return False
    
    try:
        # 验证一下 JSON 格式是否合法，防止写入坏文件
        data = json.loads(COOKIE_JSON)
        
        # 写入文件
        with open(AUTH_FILE, 'w') as f:
            json.dump(data, f)
        print("✅ 已将 Secret 写入临时 auth.json 文件")
        return True
    except json.JSONDecodeError:
        print("❌ 错误：COOKIE Secret 不是有效的 JSON 格式")
        return False

def run():
    print("🚀 启动 (StorageState 加载版)...")
    
    # 1. 准备认证文件
    if not setup_auth_file():
        send_tg("❌ 脚本停止：Cookie 格式错误或未设置")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        
        # 2. 直接从文件加载上下文 (包含 Cookie 和 LocalStorage)
        # 这是最稳的方式，因为它会恢复 Cloudflare 的挑战 Token
        try:
            context = browser.new_context(
                storage_state=AUTH_FILE,
                viewport={'width': 1920, 'height': 1080},
                user_agent=USER_AGENT or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            print("📂 已加载 Storage State (Cookie & LocalStorage)")
        except Exception as e:
            print(f"⚠️ 加载 auth.json 失败: {e}")
            context = browser.new_context()

        page = context.new_page()
        page.set_default_timeout(45000)

        # 3. 访问
        print(f"👉 访问: {TARGET_URL}")
        try:
            page.goto(TARGET_URL, wait_until='domcontentloaded')
        except: pass
        
        page.wait_for_timeout(5000)

        # 4. 登录检查
        if "login" in page.url or page.locator("input[name='email']").is_visible():
            print("❌ 依然跳转到了登录页！")
            print("💡 分析：可能是缺少 cf_clearance Cookie 导致被 CF 拦截，或者 Session 已过期。")
            page.screenshot(path="login_fail.png")
            send_tg("❌ 失败：Cookie 无效，无法免登。请尝试重新提取包含 cf_clearance 的完整 Cookie。")
            browser.close()
            return

        print("✅ 免登成功！寻找 Renew 按钮...")

        # 5. 点击 Renew
        # 尝试多种定位方式
        renew_btn = None
        if page.get_by_text("Renew", exact=True).count() > 0:
             renew_btn = page.get_by_text("Renew", exact=True).first
        elif page.locator('[data-bs-target="#renew-modal"]').count() > 0:
             renew_btn = page.locator('[data-bs-target="#renew-modal"]').first
        
        if not renew_btn:
            print("ℹ️ 未找到 Renew 按钮")
            browser.close()
            return

        renew_btn.click()
        print("⏳ 弹窗已打开，寻找验证码 Iframe...")
        time.sleep(5)

        # 6. Iframe 穿透点击 (Cloudflare 验证)
        try:
            # 查找可能是 CF 的 iframe
            target_frame = None
            for frame in page.frames:
                # Cloudflare 验证码通常包含这些关键词
                if "cloudflare" in frame.url or "turnstile" in frame.url:
                    target_frame = frame
                    print(f"✅ 锁定验证 iframe: {frame.url}")
                    break
            
            if target_frame:
                # 尝试点击 iframe 里的 checkbox
                box = target_frame.locator("input[type='checkbox']")
                body = target_frame.locator("body")
                
                if box.count() > 0:
                    print("🖱️ 点击验证 Checkbox...")
                    box.click(timeout=2000)
                else:
                    print("🖱️ Checkbox 未找到，点击 Iframe Body...")
                    body.click(timeout=2000)
                
                time.sleep(3)
            else:
                print("⚠️ 未找到特定的验证 iframe，尝试盲点弹窗中心...")
                # 备用方案：点击屏幕中央（假设弹窗在中间）
                page.mouse.click(960, 540)
                time.sleep(1)

            # 7. 提交
            print("🚀 提交续期...")
            btn = page.locator("#renew-modal button.btn-primary")
            if btn.is_visible():
                btn.click()
            else:
                page.keyboard.press("Enter")

            time.sleep(5)
            page.screenshot(path="result.png")
            
            # 检查成功标志
            if page.locator(".alert-success").is_visible() or "success" in page.content().lower():
                print("✅ 续期成功！")
                send_tg("✅ Katabump 续期成功！")
            else:
                print("❓ 流程结束，请查看截图确认结果")

        except Exception as e:
            print(f"❌ 交互错误: {e}")
            send_tg(f"❌ 运行出错: {e}")

        browser.close()

if __name__ == "__main__":
    run()
