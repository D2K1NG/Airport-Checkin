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
    payload = {"chat_id": TG_USER_ID, "text": f"🤖 VPS续期结果 (V12):\n{msg}", "parse_mode": "Markdown"}
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
    print("🚀 启动 V12 拒绝假成功版...")
    
    # 基础检查
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
            # 1. 进入页面
            print(f"1️⃣ 进入页面: {TARGET_URL}")
            page.goto(TARGET_URL, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)

            if "login" in page.url:
                raise Exception("Cookie失效，重定向回登录页")

            # 2. 打开弹窗
            print("2️⃣ 打开 Renew 弹窗...")
            try:
                page.get_by_text("Renew", exact=True).first.click()
            except:
                page.locator(".btn-primary").filter(has_text="Renew").click()
            
            page.wait_for_timeout(3000)
            
            # 确保弹窗开了
            if not page.locator(".modal-dialog").is_visible():
                raise Exception("弹窗未打开，无法继续")

            # 3. Cloudflare 验证 (死磕变绿)
            print("3️⃣ 处理 Cloudflare 验证码...")
            captcha_verified = False
            
            try:
                iframe = page.frame_locator("iframe[src*='challenges.cloudflare.com']").first
                iframe.locator("body").wait_for(timeout=8000)
                
                cb = iframe.locator("input[type='checkbox']")
                if cb.is_visible():
                    print("👆 点击验证码...")
                    # 模拟更真实点击
                    box = cb.bounding_box()
                    if box:
                        page.mouse.move(box["x"]+10, box["y"]+10)
                        time.sleep(0.2)
                        page.mouse.down()
                        time.sleep(0.1)
                        page.mouse.up()
                    else:
                        cb.click(force=True)
                    
                    print("⏳ 等待变绿...")
                    for i in range(20):
                        # 这里只检测是否变绿，绝对不当做最终成功信号
                        if iframe.get_by_text("Success").is_visible() or iframe.get_by_text("成功").is_visible():
                            print("✅ 验证码已通过 (准备下一步)")
                            captcha_verified = True
                            break
                        time.sleep(1)
                else:
                    print("⚠️ 无验证码复选框，假设已通过")
                    captcha_verified = True
            except:
                print("⚠️ 验证码加载失败或不存在")
                # 继续尝试，也许不需要验证码

            # 4. 点击最终按钮 (最关键的一步)
            print("🛑 强制等待 3 秒...")
            time.sleep(3)
            
            print("4️⃣ 点击确认续期 (Final Renew)...")
            
            # 截图记录点击前的状态
            page.screenshot(path="debug_before_click.png")
            
            # 使用 JS 强制点击弹窗里的按钮
            # 这里的逻辑是：找到弹窗里的所有按钮，点击那个包含 Renew 文字的
            js_script = """() => {
                const btns = Array.from(document.querySelectorAll('.modal-dialog button'));
                const target = btns.find(b => b.innerText.includes('Renew'));
                if(target) { 
                    target.click(); 
                    return "Clicked"; 
                }
                return "NotFound";
            }"""
            
            click_result = page.evaluate(js_script)
            print(f"👉 JS点击结果: {click_result}")
            
            if click_result == "NotFound":
                print("⚠️ JS未找到按钮，尝试 Playwright 暴力点击...")
                page.locator(".modal-footer button").last.click()

            # 5. 结果判定 (严防假成功)
            print("5️⃣ 等待结果反馈...")
            # 给服务器 5 秒处理时间
            page.wait_for_timeout(5000)
            page.screenshot(path="debug_final_status.png")

            # 判定逻辑：
            # 1. 如果有红色报错条 -> 失败
            # 2. 如果弹窗还在 -> 失败 (说明按钮没点上，或者服务器没响应)
            # 3. 只有弹窗消失了 -> 才算成功
            
            has_error = page.locator(".alert-danger").is_visible() or page.get_by_text("Please complete the captcha").is_visible()
            is_modal_open = page.locator(".modal-dialog").is_visible()
            
            msg = ""
            if has_error:
                msg = "❌ 失败：检测到红色报错 (验证码未过或请求被拒)。"
            elif is_modal_open:
                msg = "❌ 失败：操作后弹窗未关闭，说明续期按钮点击无效。"
            else:
                # 再次检查是否有特定的成功提示条
                if page.locator(".alert-success").is_visible() or "successfully" in page.content().lower():
                    msg = "✅ V12 确认成功：弹窗已关闭且检测到成功提示。"
                else:
                    # 弹窗关了，但没看见提示条，可能是隐式成功
                    msg = "✅ V12 疑似成功：弹窗已正常关闭 (未检测到报错)。"

            print(msg)
            send_telegram(msg)

        except Exception as e:
            err = f"❌ 运行报错: {str(e)}"
            print(err)
            send_telegram(err)
            try:
                page.screenshot(path="error_crash.png")
            except: pass
        finally:
            browser.close()

if __name__ == "__main__":
    run()
