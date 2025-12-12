import os
import time
import requests
from playwright.sync_api import sync_playwright

# --- 环境变量 ---
# 必须配置: COOKIE, URL
# 可选配置: TG_TOKEN, TG_USER_ID, USER_AGENT
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
        "text": f"🤖 VPS续期通知 (V18-ReverseTab):\n{msg}", 
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
    print("🚀 启动 V18 逆向焦点修复版...")
    
    if not COOKIE_STR or not TARGET_URL:
        send_telegram("❌ 致命错误：Secrets 变量 (COOKIE 或 URL) 缺失")
        exit(1)

    # 默认使用通用 UA，如果 Secrets 里有则覆盖
    final_ua = USER_AGENT if USER_AGENT else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    try:
        domain = TARGET_URL.split("/")[2]
    except:
        domain = "dashboard.katabump.com"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, # 调试时可改为 False 观看过程
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        context = browser.new_context(
            user_agent=final_ua, 
            viewport={'width': 1920, 'height': 1080}, 
            locale='zh-CN'
        )
        context.add_cookies(parse_cookies(COOKIE_STR, domain))
        page = context.new_page()

        # 注入防检测脚本
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
            print("2️⃣ 寻找并点击 Renew 按钮...")
            # 尝试点击页面上的 Renew 按钮，兼容多种 HTML 结构
            try:
                page.get_by_text("Renew", exact=True).first.click()
            except:
                # 备用：寻找 class 为 btn-primary 且包含 Renew 文本的按钮
                page.locator(".btn-primary").filter(has_text="Renew").click()
            
            print("⏳ 弹窗已触发，等待 5 秒让 Cloudflare 加载...")
            time.sleep(5)
            
            # 3. 检查弹窗是否存在 (根据你的 HTML，ID 是 renew-modal)
            modal = page.locator("#renew-modal")
            if not modal.is_visible():
                print("❌ 严重错误：弹窗未显示 (可能 Cookie 失效或按钮点击失败)")
                page.screenshot(path="debug_error_no_modal.png")
                raise Exception("弹窗丢失")

            # ==========================================
            # 核心修改：逆向 Tab 战术 (Reverse Tab Strategy)
            # ==========================================
            print("3️⃣ 执行战术：定位底部按钮 -> 反向 Tab 寻找验证码")
            
            # A. 锁定底部的 "Renew" 提交按钮 (这是 HTML 中最稳定的锚点)
            # 结构: #renew-modal -> .modal-footer -> .btn-primary
            submit_btn = modal.locator(".modal-footer .btn-primary")
            
            # 强制聚焦到底部按钮
            try:
                submit_btn.focus()
                print("📍 焦点已锁定到底部 Renew 按钮")
            except Exception as e:
                print(f"⚠️ 无法聚焦底部按钮: {e}")
            
            time.sleep(0.5)

            # B. 执行反向 Tab (Shift + Tab)
            # 路径推演：底部Renew -> (Shift+Tab) -> 底部Close -> (Shift+Tab) -> Cloudflare验证码
            print("⌨️ 执行：Shift+Tab x 2 -> Space")
            
            page.keyboard.press("Shift+Tab")
            time.sleep(0.5)
            
            page.keyboard.press("Shift+Tab")
            time.sleep(0.5)
            
            print("👆 按下 Space 激活验证...")
            page.keyboard.press("Space")
            
            # --- 补救措施：直接点击 iframe ---
            # 如果上面的键盘流没反应，尝试直接点击 iframe body
            try:
                print("🛡️ (双保险) 尝试寻找 iframe 直接点击...")
                iframe_box = modal.frame_locator("iframe[src*='challenges.cloudflare.com']").first
                # 稍微等待一下 iframe 元素
                page.wait_for_timeout(1000)
                # 点击 iframe 的 body 部分
                iframe_box.locator("body").click(timeout=3000)
                print("👉 已执行 iframe 点击")
            except:
                print("ℹ️ 未能直接点击 iframe (可能键盘流已生效或 iframe 未加载)")

            # 4. 等待验证通过
            print("⏳ 等待变绿 (检查 Success 标记)...")
            captcha_passed = False
            
            # 轮询检查 20 秒
            for i in range(20):
                if i == 1: page.screenshot(path="debug_checking_captcha.png")
                
                # 检查所有 frame 中是否有 "Success" 或 "成功"
                for frame in page.frames:
                    try:
                        if frame.get_by_text("Success").is_visible() or frame.get_by_text("成功").is_visible():
                            print("✅ 验证码变绿！(Captured Success)")
                            captcha_passed = True
                            break
                    except: pass
                
                if captcha_passed: break
                time.sleep(1)

            # 5. 点击提交
            if captcha_passed:
                print("4️⃣ 验证通过，点击最终 Renew 提交...")
                page.wait_for_timeout(1000)
                submit_btn.click()
                print("✅ 提交动作已执行")
            else:
                print("⛔ 验证未通过，尝试强行提交 (死马当活马医)...")
                page.screenshot(path="debug_failed_captcha.png")
                submit_btn.click()

            # 6. 结果检查
            print("5️⃣ 最终结果检查...")
            page.wait_for_timeout(5000) # 等待网页响应
            page.screenshot(path="debug_final.png")

            # 判定标准：弹窗消失 = 成功；弹窗还在且有红字 = 失败
            if not modal.is_visible():
                msg = "✅ 续期成功：弹窗已关闭！"
            elif page.locator(".alert-danger").is_visible():
                msg = "❌ 失败：网站提示验证未通过或错误。"
            elif page.locator(".modal-dialog").is_visible():
                msg = "⚠️ 警告：弹窗未关闭，可能未提交成功。"
            else:
                msg = "✅ 续期可能成功 (弹窗消失)。"

            print(msg)
            send_telegram(msg)

        except Exception as e:
            err = f"❌ 运行报错: {str(e)}"
            print(err)
            page.screenshot(path="debug_error.png")
            send_telegram(err)
        finally:
            browser.close()

if __name__ == "__main__":
    run()
