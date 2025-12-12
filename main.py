import os
import time
import random
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
    payload = {"chat_id": TG_USER_ID, "text": f"🤖 VPS续期通知 (V11):\n{msg}", "parse_mode": "Markdown"}
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
    print("🚀 启动 V11 强制顺序版...")
    if not COOKIE_STR or not TARGET_URL:
        send_telegram("❌ 错误：Secrets 变量缺失")
        exit(1)

    # 必须使用抓包时的 UA
    final_ua = USER_AGENT if USER_AGENT else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    try:
        domain = TARGET_URL.split("/")[2]
    except:
        domain = "dashboard.katabump.com"

    with sync_playwright() as p:
        # 启动浏览器，移除自动化特征
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        context = browser.new_context(user_agent=final_ua, viewport={'width': 1920, 'height': 1080}, locale='zh-CN')
        context.add_cookies(parse_cookies(COOKIE_STR, domain))
        page = context.new_page()

        # 注入隐身代码，防止被判定为机器人
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
            print("2️⃣ 点击 Renew 打开弹窗...")
            try:
                # 优先点击文本为 Renew 的按钮
                page.get_by_text("Renew", exact=True).first.click()
            except:
                # 备用方案
                page.locator(".btn-primary").filter(has_text="Renew").click()
            
            page.wait_for_timeout(3000)
            page.screenshot(path="debug_step2_modal_open.png")

            # 3. 核心步骤：处理验证码（必须先做这一步！）
            print("3️⃣ 正在处理 Cloudflare 验证码 (白色确认框)...")
            captcha_passed = False
            
            try:
                # 定位 iframe
                iframe = page.frame_locator("iframe[src*='challenges.cloudflare.com']").first
                # 等待 iframe 加载出来
                iframe.locator("body").wait_for(timeout=10000)
                
                # 寻找那个复选框
                checkbox = iframe.locator("input[type='checkbox']")
                
                if checkbox.is_visible():
                    print("👆 找到验证框，正在点击...")
                    
                    # 模拟人类操作：先移动鼠标过去，稍微停顿，再点击
                    box = checkbox.bounding_box()
                    if box:
                        page.mouse.move(box["x"] + 10, box["y"] + 10)
                        time.sleep(0.5)
                        page.mouse.down()
                        time.sleep(0.1)
                        page.mouse.up()
                    else:
                        checkbox.click(force=True)
                    
                    # --- 死等变绿 ---
                    print("⏳ 点击完毕，等待变绿 (Success/成功)...")
                    for i in range(20): # 最多等20秒
                        # 检查是否有成功的文字出现
                        if iframe.get_by_text("Success").is_visible() or iframe.get_by_text("成功").is_visible():
                            print("✅ 验证通过！(检测到成功标志)")
                            captcha_passed = True
                            break
                        # 还没变绿？每秒检查一次
                        time.sleep(1)
                else:
                    print("👀 未找到复选框，可能已自动通过...")
                    captcha_passed = True # 没框通常意味着通过了
            
            except Exception as e:
                print(f"验证码处理异常: {e}")
            
            # 截图留证：点 Renew 前，验证码到底过没过？
            page.screenshot(path="debug_step3_captcha_status.png")

            # 4. 点击 Renew（仅当验证通过时）
            if captcha_passed:
                print("🛑 强制等待 3 秒，确保服务器接收到验证结果...")
                time.sleep(3)
                
                print("4️⃣ 点击最终 Renew 按钮...")
                
                # 使用 JS 点击，确保点的是弹窗里的按钮
                js_click = """() => {
                    // 找到所有按钮
                    const btns = Array.from(document.querySelectorAll('button'));
                    // 筛选出在弹窗(modal)里，且文字包含 Renew 的按钮
                    const target = btns.find(b => 
                        b.innerText.includes('Renew') && 
                        b.closest('.modal-dialog')
                    );
                    if(target) { 
                        target.click(); 
                        return true; 
                    }
                    return false;
                }"""
                
                if not page.evaluate(js_click):
                    # 如果 JS 没点到，尝试暴力点击最后一个可见的 Renew
                    print("⚠️ JS未找到按钮，尝试备用点击...")
                    all_renews = page.get_by_role("button", name="Renew").all()
                    # 倒序点击（通常弹窗的按钮在 HTML 结构最后面）
                    for btn in reversed(all_renews):
                        if btn.is_visible():
                            btn.click()
                            break
                
                print("✅ 已执行点击操作")
            else:
                print("⛔ 验证码未通过！跳过 Renew 点击，避免报错。")
                send_telegram("❌ 失败：验证码点不亮，GitHub IP 可能被拉黑。")
                # 强制退出，不执行后续截图
                exit(1)

            # 5. 结果检查
            print("5️⃣ 等待结果...")
            page.wait_for_timeout(5000)
            page.screenshot(path="debug_step5_final.png")
            
            # 再次检查有没有红条报错
            if page.locator("text=Please complete the captcha").is_visible():
                msg = "❌ 失败：点击太快或验证失效 (Please complete the captcha)。"
            elif "success" in page.content().lower() or "extended" in page.content().lower():
                msg = "✅ V11 续期成功！"
            else:
                msg = "⚠️ 操作结束，未检测到明确结果，请查看截图。"

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
