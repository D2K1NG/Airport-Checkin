import time
import os
import sys
import shutil # 用于清理旧视频目录
from playwright.sync_api import sync_playwright

# ==========================================
# 👇 变量配置区域 👇
# ==========================================
URL = "https://dashboard.katabump.com/servers/edit?id=180484"
VIDEO_DIR = "videos" # 视频保存目录

# 获取 GitHub 环境变量
GMAIL = os.environ.get("GMAIL")
KATAMIMA = os.environ.get("KATAMIMA")

if not GMAIL or not KATAMIMA:
    print("❌ 错误：未检测到环境变量 GMAIL 或 KATAMIMA")
    print("请检查 GitHub Secrets 和 Workflow 配置文件。")
    sys.exit(1)

# ==========================================

def run():
    print("🚀 启动 GitHub Actions 自动续期 (含全程度录屏)...")

    # 每次运行前清理并重新创建视频目录，防止文件堆积
    if os.path.exists(VIDEO_DIR):
        shutil.rmtree(VIDEO_DIR)
    os.makedirs(VIDEO_DIR, exist_ok=True)
    print(f"📁 视频目录已就绪: {VIDEO_DIR}/")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, 
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )

        # 👇👇👇 核心修改：配置录屏参数 👇👇👇
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale='zh-CN',
            record_video_dir=VIDEO_DIR, # 指定视频保存目录
            record_video_size={"width": 1920, "height": 1080} # 视频分辨率
        )
        
        page = context.new_page()
        page.set_default_timeout(60000)

        print(f"👉 前往: {URL}")
        try:
            page.goto(URL, wait_until='domcontentloaded')
        except:
            pass
        page.wait_for_timeout(3000)

        # --- 自动登录逻辑 ---
        if "login" in page.url or page.locator("#email").is_visible():
            print("🛑 执行登录流程...")
            try:
                page.fill("#email", GMAIL)
                page.fill("#password", KATAMIMA)
                
                if page.locator("#rememberMe").is_visible():
                    page.check("#rememberMe")
                
                page.click("#submit")
                
                print("⏳ 等待跳转...")
                page.wait_for_url(lambda u: "login" not in u, timeout=30000)
                print("✅ 登录成功跳转！")
                
                if URL not in page.url:
                    page.goto(URL)
                    page.wait_for_timeout(3000)
            except Exception as e:
                print(f"❌ 登录失败: {e}")
                page.screenshot(path="login_error.png")
                # 即使失败，关闭浏览器时也会保存已录制的内容
                browser.close() 
                sys.exit(1)

        # --- Renew 流程 ---
        print("\n🤖 寻找 Renew 按钮...")
        try:
            if page.locator('[data-bs-target="#renew-modal"]').is_visible():
                page.locator('[data-bs-target="#renew-modal"]').click()
            elif page.get_by_text("Renew", exact=True).count() > 0:
                page.get_by_text("Renew", exact=True).first.click()
            else:
                print("⚠️ 没找到 Renew 按钮")
        except:
            pass

        print(f"⏳ 触发弹窗，死等 20 秒...")
        time.sleep(20)

        # --- 键盘流验证 ---
        print("⚡ 开始键盘流验证...")
        try:
            page.locator("#renew-modal .modal-body").click(force=True)
        except: 
            pass

        time.sleep(1)
        print("⌨️  Tab x 2 -> Space")
        page.keyboard.press("Tab")
        time.sleep(0.5)
        page.keyboard.press("Tab")
        time.sleep(0.5)
        page.keyboard.press("Space")
        
        print("⏳ 等待 5 秒验证生效...")
        time.sleep(5)

        print("🚀 提交 Renew...")
        try:
            btn = page.locator("#renew-modal button.btn-primary", has_text="Renew")
            if btn.is_visible():
                btn.click()
            else:
                page.keyboard.press("Enter")
        except:
            pass

        print("⏳ 等待结果...")
        time.sleep(5)
        
        # --- 结果判定 ---
        page.screenshot(path="result.png") 

        if page.locator("div.alert-success").is_visible():
            print("✅✅✅ 续期成功 (Success)！")
        elif page.get_by_text("You can't renew your server yet").is_visible():
            print("🕒 未到时间 (Too Early)。脚本运行正常。")
        elif page.locator("div.alert-danger").is_visible():
            print("❌ 续期失败：网站报错 (Error)。")
        else:
            print("❓ 未知状态，请查看截图。")

        # 关闭浏览器上下文会触发视频文件写入磁盘
        context.close()
        print(f"📹 全程操作录屏已保存至 {VIDEO_DIR}/ 目录。")
        browser.close()

if __name__ == "__main__":
    run()
