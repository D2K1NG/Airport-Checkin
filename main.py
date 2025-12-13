import time
import random
import os
import requests
from playwright.sync_api import sync_playwright
# 引入反爬虫伪装库
from playwright_stealth import stealth_sync

# ================= 配置区域 =================
TARGET_URL = os.environ.get("URL")
COOKIE_STR = os.environ.get("COOKIE") 
USER_AGENT = os.environ.get("USER_AGENT")
TG_BOT = os.environ.get("TGBOT")
TG_USER = os.environ.get("TGUSERID")
# ===========================================

def send_tg(msg):
    """发送 Telegram 通知"""
    if TG_BOT and TG_USER:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_BOT}/sendMessage", 
                          json={"chat_id": TG_USER, "text": msg, "parse_mode": "HTML"}, timeout=5)
        except: pass

def parse_cookie_string(raw_str):
    """解析原始 Cookie 字符串"""
    if not raw_str: return []
    cookies = []
    items = raw_str.split(';')
    for item in items:
        if '=' in item:
            try:
                name, value = item.strip().split('=', 1)
                cookies.append({
                    'name': name, 'value': value,
                    'domain': 'dashboard.katabump.com', 'path': '/'
                })
            except: continue
    return cookies

def human_press(page, key):
    """
    🤖 拟人化按键：模拟真实手指的按压时长 (50ms - 150ms)
    """
    hold_duration = random.uniform(0.05, 0.15)
    print(f"⌨️ 按下 {key} ({hold_duration:.3f}s)...")
    page.keyboard.down(key)
    time.sleep(hold_duration)
    page.keyboard.up(key)

def run():
    print("🚀 启动 (Stealth深度伪装 + 拟人化版)...")
    
    # 创建视频保存目录
    os.makedirs("videos", exist_ok=True)

    if not TARGET_URL or not COOKIE_STR:
        print("❌ 错误：环境变量 URL 或 COOKIE 未设置")
        return

    parsed_cookies = parse_cookie_string(COOKIE_STR)

    with sync_playwright() as p:
        # 🔥 1. 浏览器启动参数优化 (模拟真实环境)
        launch_args = [
            '--disable-blink-features=AutomationControlled', # 移除自动化特征
            '--no-sandbox',
            '--disable-infobars',
            '--window-size=1920,1080',
            '--disable-dev-shm-usage',
            '--disable-extensions',
            '--mute-audio'
        ]

        browser = p.chromium.launch(
            headless=False, # 配合 xvfb 使用，必须为 False
            args=launch_args
        )
        
        # 🔥 2. 上下文伪装 (UserAgent & 时区)
        # 使用标准的 Windows Chrome UA
        real_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=USER_AGENT or real_ua,
            locale="en-US",
            timezone_id="America/New_York",
            device_scale_factor=1,
            record_video_dir="videos/", # 开启录像
            record_video_size={"width": 1920, "height": 1080}
        )

        try:
            # 注入 Cookie
            context.add_cookies(parsed_cookies)
            
            page = context.new_page()
            
            # 🔥 3. 激活 Stealth 模块 (核心伪装)
            stealth_sync(page)
            
            # 🔥 4. 双重保险：移除 webdriver 属性
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            page.set_default_timeout(60000)

            print(f"👉 访问: {TARGET_URL}")
            try:
                page.goto(TARGET_URL, wait_until='domcontentloaded')
            except: pass
            
            # 等待页面加载
            page.wait_for_timeout(5000)

            # 登录状态检查
            if "login" in page.url or page.locator("input[name='email']").is_visible():
                print("❌ Cookie 失效，跳转到了登录页")
                page.screenshot(path="login_failed.png")
                return

            print("✅ 免登成功！")

            # --- 寻找 Renew ---
            renew_btn = None
            if page.get_by_text("Renew", exact=True).count() > 0:
                 renew_btn = page.get_by_text("Renew", exact=True).first
            elif page.locator('[data-bs-target="#renew-modal"]').count() > 0:
                 renew_btn = page.locator('[data-bs-target="#renew-modal"]').first
            
            if renew_btn:
                print("🖱️ 点击 Renew 按钮...")
                renew_btn.click()
                
                print("⏳ 等待 15 秒 (让 Cloudflare 加载)...")
                time.sleep(15)

                # ==========================================
                # 👇 拟人化验证流程
                # ==========================================
                
                print("🖱️ 鼠标随机微动 (增加真人特征)...")
                for _ in range(3):
                    page.mouse.move(random.randint(100, 800), random.randint(100, 600))
                    time.sleep(random.uniform(0.1, 0.3))
                
                print("🔒 点击弹窗文本锁定焦点...")
                try:
                    # 尝试点击具体文本，如失败则点击容器
                    page.get_by_text("This will extend the life of your server").click(force=True)
                except:
                    page.locator("#renew-modal .modal-body").click(force=True, position={"x":10, "y":10})
                
                time.sleep(1)

                print("⌨️ 执行拟人化键盘流: Tab x2 -> Space")
                
                # Tab 1
                human_press(page, "Tab")
                time.sleep(random.uniform(0.6, 1.5)) # 随机间隔
                
                # Tab 2
                human_press(page, "Tab")
                time.sleep(random.uniform(0.6, 1.5))
                
                # Space (关键一步)
                human_press(page, "Space")
                
                print("⏳ 等待 6 秒验证结果...")
                time.sleep(6)
                # ==========================================

                # 提交
                print("🚀 提交 Renew...")
                btn = page.locator("#renew-modal button.btn-primary")
                if btn.is_visible():
                    btn.click()
                else:
                    page.keyboard.press("Enter")

                time.sleep(5)
                
                # 结果判断
                if page.locator(".alert-success").is_visible() or "success" in page.content().lower():
                    print("✅✅✅ 续期成功！")
                    send_tg("✅ Katabump 续期成功！")
                elif page.get_by_text("Please complete the captcha").is_visible():
                    print("❌ 失败：Cloudflare 拦截 (即使已伪装)")
                    send_tg("❌ 失败：CF 验证未通过")
                else:
                    print("❓ 结果未知，请检查录像")

            else:
                print("ℹ️ 未找到 Renew 按钮")

        except Exception as e:
            print(f"❌ 运行出错: {e}")
            send_tg(f"❌ 脚本出错: {e}")
        
        finally:
            print("\n💾 保存录像...")
            try:
                # 关闭 context 触发视频保存
                context.close()
                browser.close()
                print("✅ 视频已保存至 videos/ 目录")
            except: pass

if __name__ == "__main__":
    run()
