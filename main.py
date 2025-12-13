import time
import random
import os
import requests
from playwright.sync_api import sync_playwright

# ================= 配置区域 =================
TARGET_URL = os.environ.get("URL")
COOKIE_STR = os.environ.get("COOKIE") 
USER_AGENT = os.environ.get("USER_AGENT")
TG_BOT = os.environ.get("TGBOT")
TG_USER = os.environ.get("TGUSERID")
# ===========================================

def send_tg(msg):
    if TG_BOT and TG_USER:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_BOT}/sendMessage", 
                          json={"chat_id": TG_USER, "text": msg, "parse_mode": "HTML"}, timeout=5)
        except: pass

def parse_cookie_string(raw_str):
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
    🤖 拟人化按键：增加物理延迟
    Cloudflare 会检测按键的 keydown 和 keyup 之间的时间差
    """
    hold = random.uniform(0.08, 0.2) # 模拟人手按下的时长
    print(f"⌨️ 拟人按下 {key} (停顿 {hold:.2f}s)...")
    page.keyboard.down(key)
    time.sleep(hold)
    page.keyboard.up(key)

def apply_native_stealth(page):
    """
    🛡️ 原生 JS 伪装注入 (无需安装 playwright-stealth 库)
    彻底解决 ImportError 问题，同时移除 webdriver 指纹
    """
    page.add_init_script("""
        // 1. 移除 webdriver 属性
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });

        // 2. 伪造插件列表 (Headless 默认是空的，这很容易暴露)
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });

        // 3. 伪造 WebGL 厂商 (防止被识别为虚拟显卡)
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return 'Intel Open Source Technology Center';
            if (parameter === 37446) return 'Mesa DRI Intel(R) Ivybridge Mobile';
            return getParameter(parameter);
        };
        
        // 4. 欺骗权限查询
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
            Promise.resolve({ state: 'granted', kind: 'permission', onchange: null }) :
            originalQuery(parameters)
        );
    """)

def run():
    print("🚀 启动 (原生伪装 + 严格Tab流程)...")
    os.makedirs("videos", exist_ok=True)

    if not TARGET_URL or not COOKIE_STR:
        print("❌ 错误：环境变量未设置")
        return

    parsed_cookies = parse_cookie_string(COOKIE_STR)

    with sync_playwright() as p:
        # 启动参数：模拟真实显示器环境
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled', 
                '--no-sandbox', 
                '--disable-infobars',
                '--window-size=1920,1080',
                '--mute-audio'
            ]
        )
        
        # 强制指定 Windows Chrome User-Agent
        real_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=USER_AGENT or real_ua,
            locale="en-US",
            timezone_id="America/New_York",
            record_video_dir="videos/",
            record_video_size={"width": 1920, "height": 1080}
        )

        try:
            context.add_cookies(parsed_cookies)
            page = context.new_page()
            
            # 🔥 注入原生伪装 (关键修复)
            apply_native_stealth(page)
            
            page.set_default_timeout(60000)

            print(f"👉 访问: {TARGET_URL}")
            try:
                page.goto(TARGET_URL, wait_until='domcontentloaded')
            except: pass
            page.wait_for_timeout(5000)

            if "login" in page.url or page.locator("input[name='email']").is_visible():
                print("❌ Cookie 失效")
                page.screenshot(path="login_failed.png")
                return

            # --- Renew 流程 ---
            renew_btn = None
            if page.get_by_text("Renew", exact=True).count() > 0:
                 renew_btn = page.get_by_text("Renew", exact=True).first
            elif page.locator('[data-bs-target="#renew-modal"]').count() > 0:
                 renew_btn = page.locator('[data-bs-target="#renew-modal"]').first
            
            if renew_btn:
                print("🖱️ 点击 Renew 按钮...")
                renew_btn.click()
                
                # 严格遵守你的要求：死等 15 秒
                print("⏳ (1/3) 严格等待 15 秒...")
                time.sleep(15)

                # ==========================================
                # 👇 拟人化操作开始
                # ==========================================
                
                # 1. 鼠标假装无意划过 (增加可信度)
                print("🖱️ 鼠标随机微动 (模拟真人)...")
                page.mouse.move(random.randint(200, 500), random.randint(200, 500))
                time.sleep(0.5)
                page.mouse.move(random.randint(600, 900), random.randint(400, 600))

                # 2. 点击文本锁定焦点 (你的核心要求)
                print("🔒 点击弹窗文本锁定焦点...")
                try:
                    # 尝试点击具体的说明文本
                    page.get_by_text("This will extend").first.click(force=True)
                except:
                    # 备用：点击弹窗主体
                    page.locator("#renew-modal .modal-body").click(force=True, position={"x":10, "y":10})
                
                time.sleep(1)

                print("⌨️ 执行键盘流: Tab x2 -> Space")
                
                # Tab 1
                human_press(page, "Tab")
                time.sleep(random.uniform(0.6, 1.2)) # 随机间隔
                
                # Tab 2
                human_press(page, "Tab")
                time.sleep(random.uniform(0.6, 1.2))
                
                # Space (带物理延迟的按下)
                human_press(page, "Space")
                
                print("⏳ 验证码勾选动作完成，等待 6 秒...")
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
                
                if page.locator(".alert-success").is_visible() or "success" in page.content().lower():
                    print("✅✅✅ 续期成功！")
                    send_tg("✅ Katabump 续期成功！")
                elif page.get_by_text("Please complete the captcha").is_visible():
                    print("❌ 失败：Cloudflare 验证未通过 (按键已模拟，但仍被拦截)")
                    send_tg("❌ 失败：CF 验证未通过")
                else:
                    print("❓ 结果未知，请查看录像")

            else:
                print("ℹ️ 未找到 Renew 按钮")

        except Exception as e:
            print(f"❌ 运行出错: {e}")
            send_tg(f"❌ 脚本出错: {e}")
        
        finally:
            print("\n💾 保存录像...")
            try:
                context.close()
                browser.close()
            except: pass

if __name__ == "__main__":
    run()
