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
        "text": f"🤖 VPS续期通知:\n{msg}", 
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
    print("🚀 启动 V23 强力验证版...")
    
    if not COOKIE_STR or not TARGET_URL:
        send_telegram("❌ 致命错误：Secrets 变量缺失")
        exit(1)

    # 使用更真实的 User-Agent 防止被识别
    final_ua = USER_AGENT if USER_AGENT else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    
    try:
        domain = TARGET_URL.split("/")[2]
    except:
        domain = "dashboard.katabump.com"

    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(
            headless=True, # 必须为 True 才能在 GitHub Actions 运行
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-setuid-sandbox']
        )
        context = browser.new_context(
            user_agent=final_ua, 
            viewport={'width': 1920, 'height': 1080}, 
            locale='zh-CN',
            timezone_id='Asia/Shanghai'
        )
        context.add_cookies(parse_cookies(COOKIE_STR, domain))
        page = context.new_page()

        # 注入防检测脚本
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page.set_default_timeout(60000) # 60秒超时

        try:
            # 1. 访问页面
            print(f"1️⃣ 进入页面: {TARGET_URL}")
            page.goto(TARGET_URL, wait_until='domcontentloaded')
            page.wait_for_timeout(5000)

            # 2. 触发弹窗
            print("2️⃣ 尝试打开 Renew 弹窗...")
            try:
                # 优先寻找按钮，找不到则找文字
                if page.locator('[data-bs-target="#renew-modal"]').is_visible():
                    page.locator('[data-bs-target="#renew-modal"]').click()
                else:
                    page.get_by_text("Renew", exact=True).first.click()
            except Exception as e:
                print(f"⚠️ 触发弹窗时遇到小问题: {e}")
            
            # --- 等待 Cloudflare 加载 ---
            print("⏳ 等待 6 秒，让验证框加载...")
            time.sleep(6)
            
            modal = page.locator("#renew-modal")
            
            # ==========================================
            # 核心攻坚：处理 Cloudflare 验证 (Turnstile)
            # ==========================================
            print("🤖 开始寻找 Cloudflare 验证框...")
            
            # 定义可能的 iframe 特征 (覆盖旧版 challenges 和新版 turnstile)
            iframe_selectors = [
                "iframe[src*='challenges']", 
                "iframe[src*='turnstile']",
                "iframe[title*='Widget']"
            ]
            
            cf_frame = None
            for selector in iframe_selectors:
                if page.locator(selector).first.is_visible():
                    print(f"✅ 发现验证框 iframe: {selector}")
                    cf_frame = page.frame_locator(selector).first
                    break
            
            if cf_frame:
                try:
                    # 策略 A: 尝试点击 input 或 label
                    print("👉 尝试点击验证框内部元素...")
                    cf_frame.locator("body").click(timeout=3000) # 先点一下 body 激活焦点
                    time.sleep(1)
                    
                    # 尝试点击 checkbox 区域 (盲点：左侧居中)
                    # 很多时候元素被混淆，但点击位置是固定的
                    box = cf_frame.locator("body").bounding_box()
                    if box:
                        # 点击 iframe 左侧约 30px 的位置，通常是勾选框所在
                        print(f"📍 坐标点击: X={box['x']+30}, Y={box['y']+30}")
                        page.mouse.click(box['x'] + 30, box['y'] + 30)
                    else:
                        # 如果拿不到坐标，尝试点 label
                        cf_frame.locator("label").click(timeout=3000)
                        
                    print("✅ 点击动作已执行")
                except Exception as e:
                    print(f"⚠️ 验证框点击尝试失败: {e}")
            else:
                print("⚠️ 未检测到明显的 iframe，可能已经被 Cloudflare 隐形验证通过，或者加载失败。")

            # 验证后的等待
            print("⏳ 等待 8 秒，让 Cloudflare 转圈...")
            time.sleep(8)
            page.screenshot(path="debug_after_captcha.png")

            # ==========================================
            # 3. 提交 Renew
            # ==========================================
            print("🚀 提交 Renew 按钮...")
            
            # 尝试在弹窗内寻找按钮
            try:
                # 定位弹窗底部的 Renew 按钮
                renew_btn = modal.locator("button.btn-primary", has_text="Renew")
                if renew_btn.is_visible():
                    renew_btn.click()
                else:
                    # 备选：有时候是用 form submit
                    modal.locator("button[type='submit']").click()
            except:
                # 最后手段：键盘操作
                print("⚠️ 按钮定位失败，使用键盘 Enter 尝试提交...")
                page.keyboard.press("Enter")

            # ==========================================
            # 4. 结果验证 (基于你提供的成功截图)
            # ==========================================
            print("⏳ 等待 5 秒检查结果...")
            time.sleep(5)
            
            # 截图看最终状态
            page.screenshot(path="debug_final_result.png")

            # 检查绿色成功条
            success_banner = page.locator("div.alert-success") # 通常包含 "Your service has been renewed"
            success_text = page.get_by_text("Your service has been renewed")
            
            if success_banner.is_visible() or success_text.is_visible():
                msg = "✅ 续期成功！检测到 'Your service has been renewed' 提示。"
            elif page.locator(".alert-danger").is_visible():
                msg = "❌ 失败：网站报错 (验证失败或 Cookies 过期)。"
            elif modal.is_visible():
                msg = "⚠️ 警告：弹窗未关闭，可能验证未通过。"
            else:
                msg = "❓ 状态未知：弹窗已消失，但未检测到明确成功提示，请检查截图。"

            print(msg)
            send_telegram(msg)

        except Exception as e:
            err = f"❌ 脚本运行崩溃: {str(e)}"
            print(err)
            # 发生崩溃时截图
            try:
                page.screenshot(path="debug_crash.png")
            except:
                pass
            send_telegram(err)
        finally:
            browser.close()

if __name__ == "__main__":
    run()
