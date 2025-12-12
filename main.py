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
    payload = {"chat_id": TG_USER_ID, "text": f"🤖 VPS续期通知 (V17):\n{msg}", "parse_mode": "Markdown"}
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
    print("🚀 启动 V17 焦点修复版...")
    
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

        # 隐身代码
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
            print("2️⃣ 点击 Renew 按钮，打开弹窗...")
            try:
                page.get_by_text("Renew", exact=True).first.click()
            except:
                page.locator(".btn-primary").filter(has_text="Renew").click()
            
            # --- 关键修改：绝对不点背景！只等待 ---
            print("⏳ 弹窗已触发，静置 5 秒 (不乱动)...")
            time.sleep(5)
            
            # 检查弹窗是否还活着 (如果之前误触关闭了，这里会报错)
            if not page.locator(".modal-dialog").is_visible():
                print("❌ 严重错误：弹窗未显示 (可能被误关或没点开)")
                page.screenshot(path="debug_error_no_modal.png")
                raise Exception("弹窗丢失")

            # 3. 设定起始焦点
            print("3️⃣ 设定焦点到弹窗头部...")
            # 我们先点击一下弹窗的“标题栏” (Renew 文字)，确保焦点在弹窗范围内，且不会触发关闭
            page.locator(".modal-title").filter(has_text="Renew").click()
            
            # 或者聚焦右上角的关闭按钮 (这是通常的 Tab 起点)
            # page.locator(".modal-header .btn-close").focus() 

            # 4. 执行您的战术：2次 Tab -> 空格
            print("⌨️ 执行：Tab x 2 -> Space")
            
            page.keyboard.press("Tab")
            time.sleep(0.5)
            
            page.keyboard.press("Tab")
            time.sleep(0.5)
            
            print("👆 按下 Space 激活验证...")
            page.keyboard.press("Space")

            # 5. 等待验证通过
            print("⏳ 等待变绿...")
            captcha_passed = False
            
            for i in range(20):
                for frame in page.frames:
                    try:
                        if frame.get_by_text("Success").is_visible() or frame.get_by_text("成功").is_visible():
                            print("✅ 验证码变绿！(Captured Success)")
                            captcha_passed = True
                            break
                    except: pass
                if captcha_passed: break
                time.sleep(1)

            # 截图看这次焦点对不对
            page.screenshot(path="debug_step3_captcha.png")

            # 6. 点击 Renew
            if captcha_passed:
                print("🛑 验证成功，等待 3 秒...")
                time.sleep(3)
                print("4️⃣ 点击最终 Renew...")
                
                # JS 强力点击
                js_click = """() => {
                    const btns = Array.from(document.querySelectorAll('.modal-dialog button'));
                    const target = btns.find(b => b.innerText.includes('Renew'));
                    if(target) { target.click(); return true; }
                    return false;
                }"""
                
                if not page.evaluate(js_click):
                    # 备用：Playwright 点击
                    page.locator(".modal-footer button").last.click()
                
                print("✅ 提交动作已执行")
            else:
                print("⛔ 验证未通过，停止提交。")
                send_telegram("❌ 失败：Tab 连招未激活验证码，请检查截图确认焦点位置。")
                exit(1)

            # 7. 结果检查
            print("5️⃣ 最终检查...")
            page.wait_for_timeout(5000)
            page.screenshot(path="debug_final.png")

            if not page.locator(".modal-dialog").is_visible():
                msg = "✅ V17 成功：弹窗已关闭！"
            elif page.locator(".alert-danger").is_visible():
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
