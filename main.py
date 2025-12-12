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
        "text": f"🤖 VPS续期通知 (V21-CustomTab):\n{msg}", 
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
    print("🚀 启动 V21 自定义 Tab 序列版...")
    
    if not COOKIE_STR or not TARGET_URL:
        send_telegram("❌ 致命错误：Secrets 变量缺失")
        exit(1)

    final_ua = USER_AGENT if USER_AGENT else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    try:
        domain = TARGET_URL.split("/")[2]
    except:
        domain = "dashboard.katabump.com"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        context = browser.new_context(
            user_agent=final_ua, 
            viewport={'width': 1920, 'height': 1080}, 
            locale='zh-CN'
        )
        context.add_cookies(parse_cookies(COOKIE_STR, domain))
        page = context.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        """)
        
        page.set_default_timeout(90000)

        try:
            # 1. 访问页面
            print(f"1️⃣ 进入页面: {TARGET_URL}")
            page.goto(TARGET_URL, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)

            # 2. 打开弹窗
            print("2️⃣ 点击 Renew 按钮，触发弹窗...")
            try:
                page.locator('[data-bs-target="#renew-modal"]').click()
            except:
                page.get_by_text("Renew", exact=True).first.click()
            
            # --- 等待弹窗和 Cloudflare 加载 ---
            print("⏳ 弹窗已触发，等待 8 秒让元素就位...")
            time.sleep(8)
            
            # 检查弹窗
            modal = page.locator("#renew-modal")
            if not modal.is_visible():
                print("❌ 严重错误：弹窗未显示")
                page.screenshot(path="debug_error_no_modal.png")
                raise Exception("弹窗丢失")

            # ==========================================
            # 核心操作：Tab x2 -> Space -> Wait 10s -> Tab x5 -> Space
            # ==========================================
            
            # A. 设定起始锚点：点击弹窗标题
            # 这一步是为了让焦点回到弹窗的最顶部，保证接下来的 "Tab x 2" 路径一致
            print("⚓ 重置焦点到弹窗标题...")
            try:
                modal.locator(".modal-title").click()
            except:
                # 如果点不到标题，就点一下弹窗左上角边缘
                modal.click(position={"x": 5, "y": 5})
            time.sleep(0.5)

            # B. 执行第一阶段：选中验证框
            print("⌨️ 执行：Tab x 2 -> 选中验证框")
            page.keyboard.press("Tab")
            time.sleep(0.5)
            page.keyboard.press("Tab")
            time.sleep(0.5)
            
            print("👆 按下 Space 激活验证...")
            page.keyboard.press("Space")

            # C. 中场等待 10 秒
            print("⏳ 验证激活后，强制等待 10 秒...")
            time.sleep(10)

            # D. 执行第二阶段：选中 Renew 按钮
            # 你的逻辑是 Tab 5 次
            print("⌨️ 执行：Tab x 5 -> 选中 Renew 按钮")
            for i in range(5):
                page.keyboard.press("Tab")
                time.sleep(0.3)
            
            # E. 确认提交
            print("🚀 按下 Space 提交 Renew...")
            page.keyboard.press("Space")
            
            # F. 等待结果反馈
            print("⏳ 等待 5 秒查看结果...")
            time.sleep(5)
            page.screenshot(path="debug_final.png")

            # 结果判定
            if not modal.is_visible():
                msg = "✅ 续期成功：弹窗已关闭！"
            elif page.locator(".alert-danger").is_visible():
                msg = "❌ 失败：网站提示验证未通过。"
            elif page.locator(".modal-dialog").is_visible():
                msg = "⚠️ 警告：弹窗未关闭，可能 Tab 次数不对或验证未完成。"
            else:
                msg = "✅ 续期可能成功 (弹窗消失)。"

            print(msg)
            send_telegram(msg)

        except Exception as e:
            err = f"❌ 运行报错: {str(e)}"
            print(err)
            send_telegram(err)
        finally:
            browser.close()

if __name__ == "__main__":
    run()
