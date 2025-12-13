import time
import os
import json
import requests
from playwright.sync_api import sync_playwright

# ==========================================
# 👇👇👇 配置区域 (自动从GitHub Secrets读取) 👇👇👇
# ==========================================
# 必须在GitHub Secrets中设置这些变量
TARGET_URL = os.environ.get("URL")
EMAIL = os.environ.get("GMAIL")
PASSWORD = os.environ.get("KATAMIMA")

# 可选：TG通知配置
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")

# 可选：将 auth.json 的全部内容复制到名为 AUTH_JSON 的 Secret 中
AUTH_JSON_CONTENT = os.environ.get("AUTH_JSON")

AUTH_FILE = "auth.json"
VIDEO_DIR = "videos/"

# ==========================================

def send_tg(message):
    """发送Telegram通知"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("⚠️ 未配置 TG 通知，跳过。")
        return
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TG_CHAT_ID, "text": message}
        requests.post(url, data=data)
        print("📢 TG 通知已发送")
    except Exception as e:
        print(f"❌ TG 发送失败: {e}")

def restore_auth_from_secret():
    """从Secret恢复Cookie文件"""
    if AUTH_JSON_CONTENT:
        print("📂 检测到 AUTH_JSON Secret，正在写入文件...")
        try:
            with open(AUTH_FILE, "w", encoding='utf-8') as f:
                f.write(AUTH_JSON_CONTENT)
            print("✅ Cookie 文件恢复成功！")
        except Exception as e:
            print(f"❌ Cookie 文件写入失败: {e}")

def run():
    print("🚀 启动 GitHub Actions 自动化脚本...")

    if not EMAIL or not PASSWORD or not TARGET_URL:
        err_msg = "❌ 错误：GitHub Secrets 环境变量未设置 (GMAIL, KATAMIMA, URL)！"
        print(err_msg)
        send_tg(err_msg)
        return

    # 尝试恢复 Cookie
    restore_auth_from_secret()

    with sync_playwright() as p:
        # ⚠️ GitHub Action 必须使用 headless=True
        print("启动浏览器 (Headless模式 + 视频录制)...")
        browser = p.chromium.launch(
            headless=True, 
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )

        # 配置录屏和视口
        context_args = {
            'viewport': {'width': 1920, 'height': 1080}, 
            'locale': 'zh-CN',
            'record_video_dir': VIDEO_DIR, # 📹 开启录屏
            'record_video_size': {'width': 1920, 'height': 1080}
        }
        
        if os.path.exists(AUTH_FILE):
            print(f"📂 加载本地/恢复的 Cookie: {AUTH_FILE}")
            context_args['storage_state'] = AUTH_FILE

        context = browser.new_context(**context_args)
        page = context.new_page()
        
        # 反爬虫特征屏蔽
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        page.set_default_timeout(60000)

        try:
            # 访问
            print(f"👉 前往目标 URL...")
            try:
                page.goto(TARGET_URL, wait_until='domcontentloaded')
            except:
                pass
            page.wait_for_timeout(3000)

            # --- 自动登录逻辑 ---
            if "login" in page.url or page.locator("#email").is_visible():
                print("🛑 Cookie 失效或不存在，执行登录...")
                try:
                    page.fill("#email", EMAIL)
                    page.fill("#password", PASSWORD)
                    if page.locator("#rememberMe").is_visible():
                        page.check("#rememberMe")
                    page.click("#submit")

                    print("⏳ 等待跳转...")
                    page.wait_for_url(lambda u: "login" not in u, timeout=30000)
                    print("✅ 登录成功")
                    
                    if TARGET_URL not in page.url:
                        page.goto(TARGET_URL)
                except Exception as e:
                    err_msg = f"❌ 登录失败: {e}"
                    print(err_msg)
                    send_tg(err_msg)
                    context.close()
                    browser.close()
                    return

            # ==========================================
            # 🤖 Renew 流程 (你的核心逻辑)
            # ==========================================
            print("\n🤖 寻找 Renew 按钮...")
            page.wait_for_timeout(2000)

            try:
                # 尝试触发弹窗
                if page.locator('[data-bs-target="#renew-modal"]').is_visible():
                    page.locator('[data-bs-target="#renew-modal"]').click()
                elif page.get_by_text("Renew", exact=True).count() > 0:
                    page.get_by_text("Renew", exact=True).first.click()
                else:
                    print("⚠️ 页面上没找到显式的 Renew 按钮 (可能已经续期或未加载)")
            except:
                pass

            print(f"⏳ 弹窗触发流程，等待 20 秒 (倒计时)...")
            for i in range(20, 0, -1):
                # GitHub Log不支持 \r 刷新，改为每5秒打印一次或直接sleep
                if i % 5 == 0:
                    print(f"倒计时: {i} ...")
                time.sleep(1)
            
            # --- 核心修复：防止 Tab 退出弹窗 ---
            print("🔒 【关键步骤】点击弹窗内部文本，锁定焦点...")
            try:
                text_el = page.locator("#renew-modal .modal-body p").first
                if text_el.is_visible():
                    text_el.click()
                else:
                    page.locator("#renew-modal .modal-content").click()
            except Exception as e:
                print(f"⚠️ 焦点锁定轻微报错: {e}")

            time.sleep(1)

            print("⌨️  按下 TAB (第1次)...")
            page.keyboard.press("Tab")
            time.sleep(0.5)

            print("⌨️  按下 TAB (第2次)...")
            page.keyboard.press("Tab")
            time.sleep(0.5)

            print("⌨️  按下 SPACE (空格) 激活验证！")
            page.keyboard.press("Space")

            print("⏳ 等待 5 秒验证生效...")
            time.sleep(5)

            print("🚀 提交 Renew...")
            try:
                submit_btn = page.locator("#renew-modal button.btn-primary", has_text="Renew")
                if submit_btn.is_visible():
                    submit_btn.click()
                else:
                    page.keyboard.press("Enter")
            except:
                pass

            print("⏳ 等待结果...")
            time.sleep(5)

            # 截图留证
            page.screenshot(path="result.png")

            status_msg = ""
            if page.locator("div.alert-success").is_visible():
                status_msg = "✅ VPS 续期成功！"
            else:
                status_msg = "ℹ️ 流程结束，请检查视频回放确认结果。"

            print(status_msg)
            send_tg(status_msg)

        except Exception as e:
            err_msg = f"❌ 运行过程中发生错误: {e}"
            print(err_msg)
            send_tg(err_msg)
            # 发生错误也截图
            try:
                page.screenshot(path="error.png")
            except:
                pass
            raise e
        finally:
            print("🔴 关闭浏览器，保存视频...")
            context.close() # 必须关闭context才能保存视频
            browser.close()

if __name__ == "__main__":
    run()
