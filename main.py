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
    payload = {"chat_id": TG_USER_ID, "text": f"🤖 VPS续期通知:\n{msg}", "parse_mode": "Markdown"}
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
    print("🚀 启动 V5 智能等待验证版...")
    
    if not COOKIE_STR or not TARGET_URL:
        send_telegram("❌ 缺变量")
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
        context = browser.new_context(user_agent=final_ua, viewport={'width': 1920, 'height': 1080})
        context.add_cookies(parse_cookies(COOKIE_STR, domain))
        page = context.new_page()
        page.set_default_timeout(90000) # 延长总超时到 90秒

        try:
            # 1. 访问管理页
            print(f"1️⃣ 进入页面: {TARGET_URL}")
            page.goto(TARGET_URL, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)

            if "login" in page.url:
                raise Exception("Cookie失效，重定向回登录页")

            # 2. 触发弹窗
            print("2️⃣ 触发 Renew 弹窗...")
            # 尝试点击页面上所有的 Renew 按钮
            try:
                page.get_by_text("Renew", exact=True).first.click()
            except:
                # 备用：点击 CSS 类名为 btn-primary 的按钮
                page.locator(".btn-primary").filter(has_text="Renew").click()
            
            page.wait_for_timeout(2000)
            page.screenshot(path="step2_modal.png")

            # 3. 处理 Cloudflare (关键修改)
            print("3️⃣ 处理 Cloudflare 验证...")
            
            iframe = None
            try:
                # 定位 iframe
                iframe = page.frame_locator("iframe[src*='challenges.cloudflare.com']").first
                iframe.locator("body").wait_for(timeout=10000) # 确保 iframe 加载完成
                
                # 点击 Checkbox
                if iframe.locator("input[type='checkbox']").is_visible():
                    print("👆 点击验证码复选框...")
                    iframe.locator("input[type='checkbox']").click(force=True)
                
                # --- 死等变绿逻辑 ---
                print("⏳ 等待验证码通过 (Looking for 'Success')...")
                # 轮询检查 iframe 里是否出现 "Success" 字样 (最多等 15秒)
                for i in range(15):
                    # 你的成功截图里显示有 "Success!" 字样
                    if iframe.get_by_text("Success").is_visible() or iframe.get_by_text("成功").is_visible():
                        print("✅ 验证码已通过！(Detected Success)")
                        break
                    
                    # 如果还没通过，稍微动一下鼠标（玄学）
                    page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                    time.sleep(1)
                else:
                    print("⚠️ 等待超时，验证码可能未自动变绿，尝试强行继续...")
            
            except Exception as e:
                print(f"Cloudflare 处理异常 (可能无验证码): {str(e)[:50]}")

            page.screenshot(path="step3_captcha_passed.png")

            # 4. 点击最终确认
            print("4️⃣ 点击最终 Renew...")
            
            # 检查是否有之前的错误提示，如果有，说明页面状态不对，刷新重试没意义，直接硬点
            if page.get_by_text("Please complete the captcha").is_visible():
                print("⚠️ 检测到之前的验证码错误提示，尝试再次点击验证码...")
                try:
                    iframe.locator("input[type='checkbox']").click(force=True)
                    page.wait_for_timeout(3000)
                except:
                    pass

            # JS 点击弹窗里的按钮
            js_click_script = """
                const buttons = Array.from(document.querySelectorAll('button'));
                const target = buttons.find(b => b.innerText.trim() === 'Renew' && b.closest('.modal-dialog'));
                if (target) { target.click(); return true; }
                return false;
            """
            if not page.evaluate(js_click_script):
                # 备用：Playwright 点击
                page.locator(".modal-footer button").last.click()

            # 5. 最终检查
            print("5️⃣ 等待结果反馈...")
            page.wait_for_timeout(5000)
            page.screenshot(path="step5_final.png")

            content = page.content().lower()
            
            # 检查红条报错 (你截图里的那个红条)
            if "please complete the captcha" in content:
                msg = "❌ 失败：验证码仍未通过 (Cloudflare 拦截)。建议：重新抓取 Cookie 或更换 IP。"
            elif "success" in content or "extended" in content:
                msg = "✅ 续期成功！(检测到 Success 信号)"
            else:
                msg = "⚠️ 脚本结束，未检测到明确结果，请查看截图 step5_final.png"

            print(msg)
            send_telegram(msg)

        except Exception as e:
            err = f"❌ 运行报错: {str(e)}"
            print(err)
            send_telegram(err)
        finally:
            browser.close()

import random # 补上漏掉的 import

if __name__ == "__main__":
    run()
