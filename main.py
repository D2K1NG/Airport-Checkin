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
    payload = {"chat_id": TG_USER_ID, "text": f"🤖 VPS续期通知 (V15):\n{msg}", "parse_mode": "Markdown"}
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
            cookies.append({'name': name.strip(), 'value': value.strip(), 'domain': domain, 'path': '/'})
    return cookies

def run():
    print("🚀 启动 V15 键盘精准连招版...")
    
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
        context = browser.new_context(user_agent=final_ua, viewport={'width': 1920, 'height': 1080}, locale='zh-CN')
        context.add_cookies(parse_cookies(COOKIE_STR, domain))
        page = context.new_page()

        # 注入隐身代码
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
            print("2️⃣ 点击 Renew 打开弹窗...")
            try:
                page.get_by_text("Renew", exact=True).first.click()
            except:
                page.locator(".btn-primary").filter(has_text="Renew").click()
            
            # --- 严格执行您的指令 ---
            print("🛑 按照指令：弹窗后强制等待 5 秒...")
            time.sleep(5)
            
            # 确保焦点在页面上
            page.mouse.click(1, 1) 

            # 3. 键盘连招：Tab x2 -> Space
            print("3️⃣ 执行键盘连招 (Tab x2 -> Space)...")
            
            # 第1次 Tab
            page.keyboard.press("Tab")
            time.sleep(0.5)
            
            # 第2次 Tab (选中验证码)
            page.keyboard.press("Tab")
            time.sleep(0.5)
            
            # 空格键 (激活验证码)
            print("👆 按下 Space 键激活验证...")
            page.keyboard.press("Space")
            
            # 4. 等待验证通过
            print("⏳ 等待变绿 (Success)...")
            captcha_passed = False
            
            # 轮询 20 秒检查结果
            for i in range(20):
                # 遍历所有 frames 找 success
                for frame in page.frames:
                    try:
                        if frame.get_by_text("Success").is_visible() or frame.get_by_text("成功").is_visible():
                            print("✅ 验证码变绿！(Captured Success)")
                            captcha_passed = True
                            break
                    except: pass
                
                if captcha_passed: break
                time.sleep(1)

            page.screenshot(path="debug_step3_captcha.png")

            # 5. 点击 Renew
            if captcha_passed:
                print("🛑 验证通过，等待 3 秒后提交...")
                time.sleep(3)
                
                print("4️⃣ 点击最终 Renew...")
                # 使用 JS 点击，最为稳妥
                js_click = """() => {
                    const btns = Array.from(document.querySelectorAll('.modal-dialog button'));
                    const target = btns.find(b => b.innerText.includes('Renew'));
                    if(target) { 
                        target.click(); 
                        return true; 
                    }
                    return false;
                }"""
                
                if not page.evaluate(js_click):
                    # 如果 JS 没点到，试试回车 (通常表单可以直接回车提交)
                    print("⚠️ JS点击未生效，尝试按 Enter 键提交...")
                    page.keyboard.press("Enter")
                
                print("✅ 提交动作已执行")
            else:
                print("⛔ 验证未通过(超时)，终止脚本。")
                send_telegram("❌ 失败：键盘连招未激活验证码 (可能Tab次数不对或IP风控)。")
                exit(1)

            # 6. 结果检查
            print("5️⃣ 最终检查...")
            page.wait_for_timeout(8000)
            page.screenshot(path="debug_final.png")

            modal_visible = page.locator(".modal-dialog").is_visible()
            has_error = page.locator(".alert-danger").is_visible()
            
            if not modal_visible and not has_error:
                msg = "✅ V15 成功：弹窗已关闭，续期完成！"
            elif has_error:
                msg = "❌ 失败：网站提示验证未通过。"
            else:
                msg = "⚠️ 失败：弹窗未关闭。"

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
