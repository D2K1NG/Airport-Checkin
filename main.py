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
        "text": f"🤖 VPS续期通知 (V22-IframeFix):\n{msg}", 
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
    print("🚀 启动 V22 智能验证版 (Fixed by Gemini)...")
    
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
        """)
        
        page.set_default_timeout(90000)

        try:
            # 1. 访问页面
            print(f"1️⃣ 进入页面: {TARGET_URL}")
            page.goto(TARGET_URL, wait_until='domcontentloaded')
            page.wait_for_timeout(5000) # 等待初始加载

            # 2. 打开弹窗
            print("2️⃣ 点击 Renew 按钮，触发弹窗...")
            try:
                # 优先尝试更精准的选择器
                page.locator('[data-bs-target="#renew-modal"]').click()
            except:
                page.get_by_text("Renew", exact=True).first.click()
            
            # --- 等待弹窗加载 ---
            print("⏳ 弹窗已触发，等待 Cloudflare 加载...")
            time.sleep(5)
            
            modal = page.locator("#renew-modal")
            if not modal.is_visible():
                print("❌ 严重错误：弹窗未显示")
                page.screenshot(path="debug_error_no_modal.png")
                raise Exception("弹窗丢失")

            # ==========================================
            # 核心修改：使用 Frame Locator 穿透 iframe 点击验证
            # ==========================================
            
            print("🤖 正在寻找 Cloudflare 验证框 (Iframe模式)...")
            
            try:
                # 1. 找到包含 'challenges' 或 'turnstile' 的 iframe
                # 这是 Cloudflare 验证码的标准特征
                cf_iframe = page.frame_locator("iframe[src*='challenges']")
                
                # 2. 在 iframe 内部定位元素
                # 使用你之前提取的 xpath，但在 iframe 上下文中使用
                print("🎯 尝试点击验证框...")
                
                # 设置较短的超时，如果找不到就尝试备用方案
                try:
                    cf_iframe.locator("xpath=/html/body//div/div/div[1]/div/label/input").click(timeout=5000)
                except:
                    # 如果 input 点不到，尝试点 label（有时候 input 是隐藏的）
                    cf_iframe.locator("label").first.click(timeout=5000)
                    
                print("✅ 已发送点击指令给验证框")
            except Exception as e:
                print(f"⚠️ 验证框点击遇到状况 (可能已自动通过或未加载): {str(e)}")
                # 截图以供调试
                page.screenshot(path="debug_iframe_error.png")

            # 验证后的强制等待，给 Cloudflare 转圈圈的时间
            print("⏳ 验证点击后，等待 8 秒...")
            time.sleep(8)

            # ==========================================
            # 提交 Renew
            # ==========================================
            
            print("🚀 提交 Renew...")
            # 不再使用 Tab x 5，直接在 modal 里找 Renew 按钮点击
            try:
                # 在弹窗 (#renew-modal) 内部寻找文字为 "Renew" 的按钮
                # 并确保它是可见的
                renew_btn = modal.locator("button", has_text="Renew").locator("visible=true")
                renew_btn.click()
            except Exception as e:
                print(f"⚠️ 直接点击按钮失败，尝试回退到键盘操作: {e}")
                # 保底方案：如果上面的找不到，再试一次 Tab 大法
                page.keyboard.press("Tab")
                page.keyboard.press("Tab")
                page.keyboard.press("Tab")
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
                msg = "⚠️ 警告：弹窗未关闭，可能是验证没点上或服务器响应慢。"
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
