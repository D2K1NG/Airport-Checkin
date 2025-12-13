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
        "text": f"🤖 VPS续期通知 (V25-VisualClick):\n{msg}", 
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
    print("🚀 启动 V25 视觉坐标强制点击版...")
    
    if not COOKIE_STR or not TARGET_URL:
        send_telegram("❌ 致命错误：Secrets 变量缺失")
        exit(1)

    final_ua = USER_AGENT if USER_AGENT else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    
    try:
        domain = TARGET_URL.split("/")[2]
    except:
        domain = "dashboard.katabump.com"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-setuid-sandbox']
        )
        
        # 录屏配置
        context = browser.new_context(
            user_agent=final_ua, 
            viewport={'width': 1920, 'height': 1080}, 
            locale='zh-CN',
            record_video_dir="videos/", 
            record_video_size={"width": 1920, "height": 1080}
        )
        
        context.add_cookies(parse_cookies(COOKIE_STR, domain))
        page = context.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page.set_default_timeout(60000)

        try:
            print(f"1️⃣ 进入页面: {TARGET_URL}")
            page.goto(TARGET_URL, wait_until='domcontentloaded')
            page.wait_for_timeout(5000)

            print("2️⃣ 尝试打开 Renew 弹窗...")
            try:
                if page.locator('[data-bs-target="#renew-modal"]').is_visible():
                    page.locator('[data-bs-target="#renew-modal"]').click()
                else:
                    page.get_by_text("Renew", exact=True).first.click()
            except Exception as e:
                print(f"⚠️ 触发弹窗问题: {e}")
            
            # 等待弹窗完全浮现
            time.sleep(3)
            modal = page.locator("#renew-modal")
            
            # ==========================================
            # V25 核心逻辑：视觉定位 + 物理点击
            # ==========================================
            print("🤖 寻找验证框 iframe (位置匹配模式)...")
            
            # 策略：不找名字，直接找弹窗里的 iframe 元素
            # 只要弹窗里有 iframe，我们就默认它是验证码
            target_iframe = modal.locator("iframe").first
            
            try:
                # 等待 iframe 出现
                target_iframe.wait_for(state="visible", timeout=10000)
                print("✅ 找到了弹窗内的 iframe！")
                
                # 获取它的坐标盒子 (Bounding Box)
                box = target_iframe.bounding_box()
                
                if box:
                    print(f"📍 iframe 坐标: x={box['x']}, y={box['y']}, w={box['width']}, h={box['height']}")
                    
                    # 计算中心点偏左的位置 (通常勾选框在左边)
                    # 我们让鼠标先移动过去，录屏能看到
                    click_x = box['x'] + 30  # 靠左 30px
                    click_y = box['y'] + (box['height'] / 2) # 高度居中
                    
                    print(f"🖱️ 鼠标准备移动到: {click_x}, {click_y}")
                    
                    # 1. 移动鼠标 (steps=10 让移动过程在视频里可见)
                    page.mouse.move(click_x, click_y, steps=20)
                    time.sleep(0.5)
                    
                    # 2. 点击
                    print("👇 执行物理点击...")
                    page.mouse.down()
                    time.sleep(0.1)
                    page.mouse.up()
                    
                    # 3. 再点一次中心点保险 (防止上面点偏)
                    center_x = box['x'] + (box['width'] / 2)
                    center_y = box['y'] + (box['height'] / 2)
                    page.mouse.move(center_x, center_y, steps=10)
                    page.mouse.click(center_x, center_y)
                    
                else:
                    print("⚠️ 无法获取 iframe 坐标，尝试盲点...")
                    target_iframe.click()

            except Exception as e:
                print(f"❌ 验证框定位失败: {e}")
                print("尝试备用方案：键盘 Tab 盲操作")
                # 备用：猛按 Tab
                page.locator(".modal-title").click() # 重置焦点
                for _ in range(3):
                    page.keyboard.press("Tab")
                    time.sleep(0.2)
                page.keyboard.press("Space")

            
            print("⏳ 点击完成，等待 10 秒让验证通过...")
            time.sleep(10)

            # ==========================================
            # 提交 Renew
            # ==========================================
            print("🚀 提交 Renew...")
            try:
                # 再次定位按钮，防止 DOM 刷新
                renew_btn = page.locator("#renew-modal button.btn-primary", has_text="Renew")
                if renew_btn.is_visible():
                    renew_btn.click()
                else:
                    modal.locator("button[type='submit']").click()
            except:
                page.keyboard.press("Enter")

            print("⏳ 等待结果...")
            time.sleep(5)
            
            # --- 结果判定 ---
            if page.locator("div.alert-success").is_visible() or page.get_by_text("Your service has been renewed").is_visible():
                msg = "✅ 续期成功！检测到成功提示。"
            elif page.locator(".alert-danger").is_visible():
                msg = "❌ 失败：网站报错。"
            elif modal.is_visible():
                msg = "⚠️ 警告：弹窗未关闭，验证可能未通过。"
            else:
                msg = "❓ 状态未知 (弹窗消失)。"

            print(msg)
            send_telegram(msg)

        except Exception as e:
            err = f"❌ 运行崩溃: {str(e)}"
            print(err)
            send_telegram(err)
        finally:
            context.close()
            browser.close()

if __name__ == "__main__":
    run()
