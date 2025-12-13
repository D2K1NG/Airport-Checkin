import time
import os
import json  # 新增: 用于解析 JSON
import requests
from playwright.sync_api import sync_playwright

# ==========================================
# 👇👇👇 环境变量映射区域 👇👇👇
# ==========================================
# 必填项
TARGET_URL = os.environ.get("URL")
EMAIL = os.environ.get("GMAIL")
PASSWORD = os.environ.get("KATAMIMA")

# 敏感数据：Cookie (来自 Secret)
COOKIE_JSON = os.environ.get("COOKIE") 

# 选填项
USER_AGENT_STR = os.environ.get("USER_AGENT")
TG_BOT_TOKEN = os.environ.get("TGBOT")
TG_USER_ID = os.environ.get("TGUSERID")

AUTH_FILE = "auth.json"  # 运行时生成的临时文件名
# ==========================================

def send_telegram(message):
    """发送 Telegram 通知"""
    if not TG_BOT_TOKEN or not TG_USER_ID:
        return
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_USER_ID,
        "text": f"🤖 Katabump 通知:\n{message}",
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def restore_cookie():
    """
    安全核心：尝试从 Secret (环境变量) 恢复 auth.json
    """
    if COOKIE_JSON:
        print("🔐 检测到 COOKIE Secret，正在还原为临时会话文件...")
        try:
            # 尝试解析 JSON 字符串
            cookie_data = json.loads(COOKIE_JSON)
            # 写入运行时文件系统 (不会上传到仓库)
            with open(AUTH_FILE, 'w') as f:
                json.dump(cookie_data, f)
            print("✅ 临时 auth.json 创建成功！")
            return True
        except json.JSONDecodeError:
            print("⚠️ COOKIE Secret 格式错误 (非标准 JSON)，跳过加载。")
    return False

def run():
    if not EMAIL or not PASSWORD or not TARGET_URL:
        print("❌ 错误：环境变量 (GMAIL, KATAMIMA, URL) 未设置！")
        return

    print("🚀 启动脚本...")
    
    # 1. 优先从 Secret 恢复 Cookie
    # 如果 Secret 没填，后面会尝试读取 Cache 里的文件（如果有的话）
    restore_cookie()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, # 配合 xvfb
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )

        context_options = {
            'viewport': {'width': 1920, 'height': 1080}, 
            'locale': 'zh-CN'
        }
        if USER_AGENT_STR:
            context_options['user_agent'] = USER_AGENT_STR

        # 2. 加载 Cookie (无论是从 Secret 还原的，还是 Cache 恢复的)
        if os.path.exists(AUTH_FILE):
            print(f"📂 加载会话文件: {AUTH_FILE}")
            context_options['storage_state'] = AUTH_FILE

        context = browser.new_context(**context_options)
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        page.set_default_timeout(60000)

        # 3. 访问与登录检测
        print(f"👉 前往目标...")
        try:
            page.goto(TARGET_URL, wait_until='domcontentloaded')
        except:
            pass
        page.wait_for_timeout(3000)

        if "login" in page.url or page.locator("#email").is_visible():
            print("🛑 Cookie 失效或不存在，执行登录...")
            try:
                page.fill("#email", EMAIL)
                page.fill("#password", PASSWORD)
                if page.locator("#rememberMe").is_visible():
                    page.check("#rememberMe")
                page.click("#submit") # 请根据实际按钮调整选择器
                
                page.wait_for_url(lambda u: "login" not in u, timeout=30000)
                print("✅ 登录成功，更新运行时 auth.json...")
                context.storage_state(path=AUTH_FILE)
                
                if TARGET_URL not in page.url:
                    page.goto(TARGET_URL)
            except Exception as e:
                err = f"登录失败: {e}"
                print(err)
                send_telegram(err)
                browser.close()
                return

        # 4. Renew 逻辑 (保持原有逻辑)
        print("🤖 检查 Renew...")
        page.wait_for_timeout(2000)
        
        renew_triggered = False
        try:
            if page.locator('[data-bs-target="#renew-modal"]').is_visible():
                page.locator('[data-bs-target="#renew-modal"]').click()
                renew_triggered = True
            elif page.get_by_text("Renew", exact=True).count() > 0:
                page.get_by_text("Renew", exact=True).first.click()
                renew_triggered = True
        except:
            pass

        if renew_triggered:
            print("⏳ 弹窗触发，等待验证 (20s)...")
            time.sleep(20)
            
            # 焦点修复 & Tab 连招
            try:
                page.locator("#renew-modal .modal-body").click() # 简化点击背景
                time.sleep(1)
                page.keyboard.press("Tab")
                time.sleep(0.5)
                page.keyboard.press("Tab")
                time.sleep(0.5)
                page.keyboard.press("Space") # 勾选验证
                time.sleep(5)
                
                # 提交
                submit_btn = page.locator("#renew-modal button.btn-primary", has_text="Renew")
                if submit_btn.is_visible():
                    submit_btn.click()
                else:
                    page.keyboard.press("Enter")
                
                time.sleep(5)
                if page.locator("div.alert-success").is_visible():
                    send_telegram("✅ 续期成功！")
                else:
                    send_telegram("⚠️ 完成操作但未见成功提示，请检查。")
            except Exception as e:
                send_telegram(f"Renew 出错: {e}")
        else:
            print("ℹ️ 未找到 Renew 按钮")

        browser.close()

if __name__ == "__main__":
    run()
