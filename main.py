import time
import os
import requests
from playwright.sync_api import sync_playwright

# ================= 配置区域 =================
TARGET_URL = os.environ.get("URL")
COOKIE_STR = os.environ.get("COOKIE") 

# 选填配置
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

def run():
    print("🚀 启动 (录制增强版)...")
    
    # 确保视频输出目录存在
    os.makedirs("videos", exist_ok=True)

    if not TARGET_URL or not COOKIE_STR:
        print("❌ 错误：环境变量 URL 或 COOKIE 未设置")
        return

    parsed_cookies = parse_cookie_string(COOKIE_STR)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        
        # 🔴 变化1：配置视频录制
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=USER_AGENT or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            record_video_dir="videos/", # 视频保存路径
            record_video_size={"width": 1920, "height": 1080}
        )

        # 🔴 变化2：开启全量轨迹录制 (Trace)
        # 记录截图、快照和源码，便于事后复盘
        context.tracing.start(screenshots=True, snapshots=True, sources=True)

        page = None
        try:
            # --- 注入 Cookie ---
            context.add_cookies(parsed_cookies)
            print("✅ Cookie 注入成功")

            page = context.new_page()
            page.set_default_timeout(60000)

            # --- 访问页面 ---
            print(f"👉 访问: {TARGET_URL}")
            try:
                page.goto(TARGET_URL, wait_until='domcontentloaded')
            except: pass
            
            page.wait_for_timeout(5000)

            # --- 登录检查 ---
            if "login" in page.url or page.locator("input[name='email']").is_visible():
                print("❌ 免登失败：页面跳转到了登录页")
                send_tg("❌ 续期失败：Cookie 无效")
                page.screenshot(path="login_failed.png")
                return # 退出 try，进入 finally 保存录像

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
                print("⏳ 等待 Cloudflare 弹窗...")
                time.sleep(8) 

                # --- Iframe 穿透逻辑 ---
                target_frame = None
                for frame in page.frames:
                    if "cloudflare" in frame.url or "turnstile" in frame.url:
                        target_frame = frame
                        break
                
                if target_frame:
                    print(f"✅ 锁定验证 Iframe: {target_frame.url}")
                    try:
                        target_frame.locator("input[type='checkbox']").click(timeout=5000)
                        print("🖱️ 点击 Checkbox")
                    except:
                        target_frame.locator("body").click(timeout=5000)
                        print("🖱️ 点击 Body")
                    time.sleep(5)
                else:
                    print("⚠️ 未找到验证 Iframe，盲点屏幕中央")
                    page.mouse.click(960, 540)
                    time.sleep(2)

                # --- 提交 ---
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
                    print("❓ 未检测到成功提示")
            else:
                print("ℹ️ 未找到 Renew 按钮")

        except Exception as e:
            print(f"❌ 运行出错: {e}")
            send_tg(f"❌ 脚本出错: {e}")
        
        finally:
            # 🔴 变化3：保存录制结果
            print("\n💾 正在保存录制数据...")
            
            # 1. 停止并保存 Trace
            try:
                context.tracing.stop(path="trace.zip")
                print("✅ 轨迹文件已保存: trace.zip")
            except: pass

            # 2. 关闭 Context 以保存视频
            try:
                context.close()
                browser.close()
                print("✅ 视频文件已保存至 videos/ 目录")
            except: pass

if __name__ == "__main__":
    run()
