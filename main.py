import time
import os
import requests
from playwright.sync_api import sync_playwright

# ================= 配置区域 =================
TARGET_URL = os.environ.get("URL")import time
import random # 新增：用于生成随机时间
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
    🤖 拟人化按键：模拟真实手指的按压时长
    """
    # 随机按下的时长 (0.05秒 ~ 0.2秒)
    hold_duration = random.uniform(0.05, 0.2)
    
    print(f"⌨️ 按下 {key} (持续 {hold_duration:.3f}s)...")
    page.keyboard.down(key)
    time.sleep(hold_duration)
    page.keyboard.up(key)

def run():
    print("🚀 启动 (拟人化键盘版)...")
    os.makedirs("videos", exist_ok=True)

    if not TARGET_URL or not COOKIE_STR:
        print("❌ 错误：环境变量未设置")
        return

    parsed_cookies = parse_cookie_string(COOKIE_STR)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=USER_AGENT or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            record_video_dir="videos/",
            record_video_size={"width": 1920, "height": 1080}
        )

        try:
            context.add_cookies(parsed_cookies)
            page = context.new_page()
            page.set_default_timeout(60000)

            print(f"👉 访问: {TARGET_URL}")
            try:
                page.goto(TARGET_URL, wait_until='domcontentloaded')
            except: pass
            page.wait_for_timeout(5000)

            if "login" in page.url:
                print("❌ Cookie 失效")
                page.screenshot(path="login_failed.png")
                return

            # --- 寻找 Renew ---
            renew_btn = None
            if page.get_by_text("Renew", exact=True).count() > 0:
                 renew_btn = page.get_by_text("Renew", exact=True).first
            elif page.locator('[data-bs-target="#renew-modal"]').count() > 0:
                 renew_btn = page.locator('[data-bs-target="#renew-modal"]').first
            
            if renew_btn:
                print("🖱️ 点击 Renew 按钮...")
                renew_btn.click()
                
                print("⏳ 严格等待 15 秒 (让Cloudflare加载)...")
                time.sleep(15)

                # ==========================================
                # 👇 核心：拟人化验证流程
                # ==========================================
                
                # 1. 鼠标假装“无意”晃动两下 (增加人类特征)
                print("🖱️ 鼠标随机微动 (模拟真人)...")
                page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                time.sleep(0.5)
                page.mouse.move(random.randint(600, 800), random.randint(300, 600))
                
                # 2. 点击文本锁定焦点
                print("🔒 点击弹窗文本锁定焦点...")
                try:
                    page.get_by_text("This will extend the life of your server").click(force=True)
                except:
                    page.locator("#renew-modal .modal-body").click(force=True, position={"x":10, "y":10})
                
                time.sleep(1)

                print("⌨️ 执行拟人化键盘流: Tab x2 -> Space")
                
                # Tab 1
                human_press(page, "Tab")
                # 随机间隔 0.5 ~ 1.2 秒
                time.sleep(random.uniform(0.5, 1.2))
                
                # Tab 2
                human_press(page, "Tab")
                # 随机间隔
                time.sleep(random.uniform(0.5, 1.2))
                
                # Space (关键一步：按住一小会再松开)
                human_press(page, "Space")
                
                print("⏳ 已执行空格勾选，等待 5 秒验证结果...")
                time.sleep(5)
                # ==========================================

                # 提交
                print("🚀 提交 Renew...")
                # 优先按按钮
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
                    print("❌ 失败：Cloudflare 依然拒绝了本次按键")
                    send_tg("❌ 失败：人机验证未通过 (按键已模拟，但被拒绝)")
                else:
                    print("❓ 结果未知，请检查录像")

            else:
                print("ℹ️ 未找到 Renew 按钮")

        except Exception as e:
            print(f"❌ 运行出错: {e}")
        finally:
            print("\n💾 保存录像...")
            try:
                context.close()
                browser.close()
            except: pass

if __name__ == "__main__":
    run()
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
    """
    解析原始 Cookie 字符串 (key=value; key2=value2)
    """
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

def run():
    print("🚀 启动 (Cookie登录 + 视频录制 + Tab验证)...")
    
    # 1. 创建视频目录
    os.makedirs("videos", exist_ok=True)

    if not TARGET_URL or not COOKIE_STR:
        print("❌ 错误：环境变量 URL 或 COOKIE 未设置")
        return

    parsed_cookies = parse_cookie_string(COOKIE_STR)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, # 配合 xvfb 使用
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        
        # 2. 配置上下文 (开启视频录制，关闭 Trace)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=USER_AGENT or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            record_video_dir="videos/", # 视频保存路径
            record_video_size={"width": 1920, "height": 1080}
        )
        
        # 注意：这里不再有 context.tracing.start

        try:
            # 3. 注入 Cookie
            context.add_cookies(parsed_cookies)
            print("✅ Cookie 已注入")

            page = context.new_page()
            page.set_default_timeout(60000)

            # 4. 访问页面
            print(f"👉 访问: {TARGET_URL}")
            try:
                page.goto(TARGET_URL, wait_until='domcontentloaded')
            except: pass
            
            # 等待加载
            page.wait_for_timeout(5000)

            # 5. 登录检查
            if "login" in page.url or page.locator("input[name='email']").is_visible():
                print("❌ Cookie 失效，跳转到了登录页")
                page.screenshot(path="login_failed.png")
                send_tg("❌ 失败：Cookie 无效")
                return

            print("✅ 免登成功！")

            # 6. 寻找 Renew 按钮
            renew_btn = None
            if page.get_by_text("Renew", exact=True).count() > 0:
                 renew_btn = page.get_by_text("Renew", exact=True).first
            elif page.locator('[data-bs-target="#renew-modal"]').count() > 0:
                 renew_btn = page.locator('[data-bs-target="#renew-modal"]').first
            
            if renew_btn:
                print("🖱️ 点击 Renew 按钮...")
                renew_btn.click()
                
                # ==========================================
                # 👇 核心交互逻辑 (15s 等待 + 焦点锁定 + Tab x2)
                # ==========================================
                print("⏳ 等待 15 秒 (让 Cloudflare 加载)...")
                time.sleep(15)

                print("🔒 点击弹窗文字以锁定焦点...")
                try:
                    # 点击弹窗正文，强制焦点离开 body 进入 modal
                    text_el = page.locator("#renew-modal .modal-body").first
                    # position 避免点到链接，force 确保即使被遮挡也尝试点
                    text_el.click(force=True, position={"x": 10, "y": 10})
                except:
                    # 备选：点击屏幕中心偏上
                    page.mouse.click(960, 400)

                time.sleep(1)

                print("⌨️ 执行键盘验证: Tab x2 -> Space...")
                
                # Tab 1
                page.keyboard.press("Tab")
                time.sleep(0.5)
                
                # Tab 2 (预期选中 checkbox)
                page.keyboard.press("Tab")
                time.sleep(0.5)
                
                # Space (按下)
                page.keyboard.press("Space")
                print("⌨️ 已按下 Space")

                print("⏳ 等待 5 秒验证生效...")
                time.sleep(5)
                # ==========================================

                # 7. 提交 Renew
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
                else:
                    print("❓ 未检测到成功提示 (请查看录像)")
                    # 如果页面提示验证码错误
                    if page.get_by_text("Please complete the captcha").is_visible():
                        print("❌ 失败：验证码未通过")
                        send_tg("⚠️ 失败：Tab 验证策略未通过")

            else:
                print("ℹ️ 未找到 Renew 按钮")

        except Exception as e:
            print(f"❌ 运行出错: {e}")
            send_tg(f"❌ 脚本错误: {e}")
        
        finally:
            print("\n💾 正在保存录像...")
            try:
                # 关闭 context 会自动触发视频保存
                context.close()
                browser.close()
                print("✅ 视频已保存至 videos/ 目录")
            except: pass

if __name__ == "__main__":
    run()
