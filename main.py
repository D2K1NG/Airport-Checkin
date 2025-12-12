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
    payload = {"chat_id": TG_USER_ID, "text": f"🤖 VPS续期反馈:\n{msg}", "parse_mode": "Markdown"}
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
    print("🚀 启动精准续期脚本...")
    
    if not COOKIE_STR or not TARGET_URL:
        send_telegram("❌ 缺变量")
        exit(1)

    final_ua = USER_AGENT if USER_AGENT else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    try:
        domain = TARGET_URL.split("/")[2]
    except:
        domain = "dashboard.katabump.com"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
        context = browser.new_context(user_agent=final_ua, viewport={'width': 1920, 'height': 1080})
        context.add_cookies(parse_cookies(COOKIE_STR, domain))
        page = context.new_page()
        page.set_default_timeout(60000)

        try:
            # 1. 访问主页
            print(f"1️⃣ 访问主页: https://{domain}/dashboard")
            try:
                page.goto(f"https://{domain}/dashboard", wait_until='domcontentloaded')
            except:
                pass
            page.wait_for_timeout(3000)

            if "login" in page.url:
                raise Exception("Cookie失效，已跳转回登录页")

            # 2. 跳转到管理页
            print(f"2️⃣ 跳转管理页: {TARGET_URL}")
            page.goto(TARGET_URL, wait_until='domcontentloaded')
            page.wait_for_timeout(5000)
            page.screenshot(path="step2_page.png")

            # 3. 点击主界面 Renew
            print("3️⃣ 点击主界面 Renew 按钮...")
            # 这里的逻辑是：先点页面上的，触发弹窗
            try:
                # 尝试点击页面上可见的 "Renew" 文本
                page.get_by_text("Renew", exact=True).first.click()
            except:
                print("⚠️ 主界面点击可能未触发，尝试寻找 .btn-primary")
                try:
                    page.locator(".btn-primary").filter(has_text="Renew").click()
                except:
                    print("⚠️ 没找到主按钮，假设弹窗已自动开启或无需点击")

            page.wait_for_timeout(3000)
            page.screenshot(path="step3_modal_open.png")

            # 4. 处理弹窗 (最关键的一步)
            print("4️⃣ 处理弹窗 & 验证码...")
            
            # 先处理 CF 验证码 (如果在 iframe 里)
            try:
                iframe = page.frame_locator("iframe[src*='challenges.cloudflare.com']").first
                if iframe.locator("body").is_visible():
                    print("👀 发现验证码，尝试点击...")
                    iframe.locator("input[type='checkbox']").click(force=True)
                    page.wait_for_timeout(2000)
            except:
                pass

            # 5. 点击弹窗里的“确认续期”
            print("5️⃣ 点击弹窗内的蓝色 Renew 确认按钮...")
            
            # 定位策略：找弹窗(modal)里的按钮(button)且包含文字 Renew
            # 只要这个点不到，就绝对不会成功
            clicked = False
            try:
                # 策略A: 标准 Bootstrap 弹窗结构
                modal_btn = page.locator(".modal-dialog .btn-primary").filter(has_text="Renew")
                if modal_btn.is_visible():
                    print("✅ 锁定弹窗按钮 (策略A)，点击！")
                    modal_btn.click()
                    clicked = True
            except:
                pass
            
            if not clicked:
                try:
                    # 策略B: 暴力点击页面上最后一个可见的 Renew 按钮 (通常弹窗按钮在 HTML 最后)
                    print("⚠️ 策略A失败，尝试策略B (点击最后一个可见Renew)...")
                    visible_renews = page.get_by_role("button", name="Renew").all()
                    # 过滤出可见的
                    for btn in reversed(visible_renews):
                        if btn.is_visible():
                            btn.click()
                            print("✅ 点击了最后一个可见的 Renew 按钮")
                            clicked = True
                            break
                except:
                    pass

            if not clicked:
                raise Exception("无法定位到弹窗里的确认按钮，续期中断")

            # 6. 等待结果反馈
            print("6️⃣ 等待响应...")
            page.wait_for_timeout(5000) # 给服务器 5秒 处理时间
            page.screenshot(path="step6_result.png")

            # 7. 智能结果判断 (不只看 Success 单词)
            content_text = page.locator("body").inner_text().lower()
            
            # 只有出现具体的提示语才算成功
            # 常见的提示语: "server renewed", "expiration date updated", "extended"
            success_keywords = ["successfully", "extended", "updated", "success"]
            
            # 获取页面上弹出的提示条 (Toast / Alert)
            alert_text = ""
            try:
                # 尝试抓取浮动提示内容
                if page.locator(".alert").is_visible():
                    alert_text = page.locator(".alert").inner_text()
                elif page.locator(".toast").is_visible():
                    alert_text = page.locator(".toast").inner_text()
                elif page.locator(".swal2-title").is_visible(): # SweetAlert
                    alert_text = page.locator(".swal2-title").inner_text()
            except:
                pass

            msg = ""
            if alert_text:
                print(f"📢 捕获到网页提示: {alert_text}")
                msg = f"✅ 操作完成，网页提示: {alert_text}"
            elif any(k in content_text for k in success_keywords):
                msg = "⚠️ 未捕获明确弹窗，但页面包含 Success/Extended 字样。请人工复核。"
            else:
                msg = "❌ 未检测到成功信号。可能是 Cloudflare 拦截了请求，或者按钮点击无效。"

            print(msg)
            send_telegram(msg)

        except Exception as e:
            err = f"❌ 运行出错: {str(e)}"
            print(err)
            send_telegram(err)
            try:
                page.screenshot(path="error_crash.png")
            except:
                pass
        finally:
            browser.close()

if __name__ == "__main__":
    run()
