import time
import os
import json
import requests
from playwright.sync_api import sync_playwright

# ==========================================
# 👇 环境变量与配置
# ==========================================
TARGET_URL = os.environ.get("URL")
COOKIE_JSON = os.environ.get("COOKIE") # 必须包含 auth.json 的内容
USER_AGENT_STR = os.environ.get("USER_AGENT")
TG_BOT_TOKEN = os.environ.get("TGBOT")
TG_USER_ID = os.environ.get("TGUSERID")

AUTH_FILE = "auth.json"

def send_telegram(message):
    """发送 TG 通知"""
    if not TG_BOT_TOKEN or not TG_USER_ID: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
            json={"chat_id": TG_USER_ID, "text": f"🤖 Katabump:\n{message}", "parse_mode": "HTML"},
            timeout=10
        )
    except: pass

def prepare_auth_file():
    """
    核心修复：处理 Secret 中的 Cookie 并写入 auth.json
    支持两种格式：
    1. 标准 Playwright 格式: {"cookies": [...], "origins": [...]}
    2. 纯列表格式: [{"name": "...", ...}] (自动转换)
    """
    if not COOKIE_JSON:
        print("⚠️ 警告：未检测到 COOKIE Secret！")
        return False

    try:
        data = json.loads(COOKIE_JSON)
        final_data = data
        
        # 兼容性修复：如果是列表（[{}, {}]），封装成 Playwright 标准格式
        if isinstance(data, list):
            print("ℹ️ 检测到 Cookie 为列表格式，正在封装...")
            final_data = {"cookies": data, "origins": []}
        
        with open(AUTH_FILE, 'w') as f:
            json.dump(final_data, f)
        
        print("✅ auth.json 已成功生成！")
        return True
    except json.JSONDecodeError:
        print("❌ COOKIE Secret 格式错误（不是有效的 JSON）！")
        return False
    except Exception as e:
        print(f"❌生成 auth.json 失败: {e}")
        return False

def run():
    if not TARGET_URL:
        print("❌ 缺少 URL 环境变量")
        return

    # 1. 准备 Cookie 文件
    has_cookie = prepare_auth_file()

    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(
            headless=False, # 必须配合 xvfb
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )

        # 配置上下文
        context_opts = {
            'viewport': {'width': 1920, 'height': 1080},
            'locale': 'en-US', # 建议用英文，避免字符编码问题
            'device_scale_factor': 1,
        }
        if USER_AGENT_STR: 
            context_opts['user_agent'] = USER_AGENT_STR
        
        # 🔥 关键：在这里挂载 auth.json
        if has_cookie and os.path.exists(AUTH_FILE):
            print("📂 正在挂载 Cookie...")
            context_opts['storage_state'] = AUTH_FILE
        else:
            print("⚠️ 未加载 Cookie，即将以游客身份访问（可能会跳转登录页）")

        context = browser.new_context(**context_opts)
        page = context.new_page()
        
        # 防检测注入
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        page.set_default_timeout(40000) # 40秒超时

        print(f"👉 访问: {TARGET_URL}")
        try:
            page.goto(TARGET_URL, wait_until='networkidle') # 等待网络空闲，确保加载完成
        except Exception as e:
            print(f"⚠️ 页面加载超时: {e}")

        page.wait_for_timeout(3000)

        # 2. 登录状态检测 (如果跳转到了 login，直接报错，不再尝试账号密码登录)
        if "login" in page.url or page.locator("input[type='password']").is_visible():
            err_msg = "❌ Cookie 无效或已过期！已跳转至登录页。\n请更新 GitHub Secret 中的 COOKIE 值。"
            print(err_msg)
            
            # 截图留证
            page.screenshot(path="login_failed.png")
            print("📸 已截图: login_failed.png")
            
            send_telegram(err_msg)
            browser.close()
            return # ⛔️ 终止运行，不输入账号密码

        print("✅ Cookie 有效，已在 Dashboard 页面。")

        # 3. 寻找 Renew 按钮
        renew_btn = None
        # 尝试几种定位器
        if page.locator('[data-bs-target="#renew-modal"]').is_visible():
            renew_btn = page.locator('[data-bs-target="#renew-modal"]')
        elif page.get_by_text("Renew", exact=True).is_visible():
            renew_btn = page.get_by_text("Renew", exact=True)
        
        if not renew_btn:
            print("ℹ️ 未找到可见的 Renew 按钮 (可能不需要续期)。")
            browser.close()
            return

        print("🖱️ 点击 Renew 按钮...")
        renew_btn.click()

        # 4. 处理弹窗与焦点 (重点修复)
        print("⏳ 等待弹窗加载 (15s)...")
        time.sleep(15) # 给 Cloudflare iframe 加载的时间

        try:
            # 🔥 修复焦点逻辑：点击弹窗标题或边缘，而不是正文
            # 这里的 .modal-content 是 Bootstrap 标准弹窗容器
            print("🔒 正在锁定焦点到弹窗内部...")
            
            modal = page.locator("#renew-modal .modal-content")
            if modal.is_visible():
                # 点击弹窗左上角空白处，确保焦点进入弹窗层级
                modal.click(position={"x": 20, "y": 20})
            else:
                print("⚠️ 警告：找不到 #renew-modal 元素")
            
            time.sleep(1)

            # 🎹 键盘 TAB 连招
            # 通常 Cloudflare 在 iframe 里，Tab 次数不确定，我们尝试多按几次
            print("⌨️ 开始 Tab 尝试选中验证码...")
            
            for i in range(1, 4):
                print(f"   Tab {i}...")
                page.keyboard.press("Tab")
                time.sleep(0.5)

            print("⌨️ 按下 SPACE (空格) 尝试激活验证...")
            page.keyboard.press("Space")
            
            # 再等一会，看验证是否通过
            time.sleep(5)

            # 提交逻辑
            print("🚀 尝试提交...")
            submit_btn = page.locator("#renew-modal button.btn-primary")
            if submit_btn.is_visible():
                submit_btn.click()
            else:
                page.keyboard.press("Enter")

            # 结果验证
            time.sleep(5)
            if page.locator(".alert-success").is_visible() or page.get_by_text("success").is_visible():
                msg = "✅✅✅ 续期成功！"
                print(msg)
                send_telegram(msg)
            else:
                # 再次截图查看最后状态
                page.screenshot(path="result_check.png")
                print("⚠️ 未检测到明确成功信号，已截图 result_check.png")
                send_telegram("⚠️ 脚本执行完毕，未检测到成功提示，请检查。")

        except Exception as e:
            err = f"❌ 交互流程出错: {e}"
            print(err)
            send_telegram(err)

        browser.close()

if __name__ == "__main__":
    run()
