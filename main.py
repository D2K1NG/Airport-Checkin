import os
import time
import requests
import random
from playwright.sync_api import sync_playwright

# --- 环境变量获取 ---
COOKIE_STR = os.environ.get("COOKIE")
TARGET_URL = os.environ.get("URL") # 例如: https://dashboard.katabump.com/servers/edit?id=180484
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_USER_ID = os.environ.get("TG_USER_ID")
USER_AGENT = os.environ.get("USER_AGENT")

def send_telegram(msg):
    """发送 Telegram 通知"""
    print(f"🔔 准备发送通知: {msg}")
    if not TG_TOKEN or not TG_USER_ID:
        print("⚠️ 未检测到 TG_TOKEN 或 TG_USER_ID，跳过通知。")
        return
    
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_USER_ID,
        "text": f"🤖 **VPS续期助手**\n\n{msg}",
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code != 200:
            print(f"❌ TG 发送失败: {res.text}")
    except Exception as e:
        print(f"❌ TG 网络错误: {e}")

def parse_cookies(cookie_str, domain):
    """解析 Cookie 字符串"""
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
    print("🚀 脚本开始运行...")
    
    # 1. 基础检查
    if not COOKIE_STR or not TARGET_URL:
        err = "❌ 致命错误：Secrets 中缺少 COOKIE 或 URL。"
        print(err)
        send_telegram(err)
        exit(1)

    if not USER_AGENT:
        print("⚠️ 警告：Secrets 中未设置 USER_AGENT。将使用默认值，可能会导致重定向死循环！")
    
    # 必须使用你抓包时的 UA，否则网站会认为 Cookie 是被盗用的，从而无限重定向
    final_ua = USER_AGENT if USER_AGENT else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    # 提取域名
    try:
        domain = TARGET_URL.split("/")[2]
    except:
        domain = "dashboard.katabump.com"

    with sync_playwright() as p:
        # 启动浏览器
        print("🌐 启动 Chromium...")
        browser = p.chromium.launch(
            headless=True, # Actions 中必须为 True
            args=['--disable-blink-features=AutomationControlled']
        )
        
        # 创建上下文 (模拟特定的浏览器环境)
        context = browser.new_context(
            user_agent=final_ua,
            viewport={'width': 1920, 'height': 1080},
            locale='en-US'
        )
        
        # 注入 Cookie
        context.add_cookies(parse_cookies(COOKIE_STR, domain))
        
        page = context.new_page()
        page.set_default_timeout(45000) # 增加超时时间到 45秒

        try:
            # --- 第一步：先访问 Dashboard 主页 (避免直接深层链接触发风控) ---
            dashboard_url = f"https://{domain}/dashboard"
            print(f"1️⃣ 访问主页以验证 Session: {dashboard_url}")
            
            try:
                page.goto(dashboard_url, wait_until='domcontentloaded')
            except Exception as e:
                print(f"⚠️ 访问主页时遇到重定向或超时 (可忽略): {str(e)[:100]}")
            
            page.wait_for_timeout(3000)
            page.screenshot(path="debug_step1_dashboard.png")

            # 检查是否掉登录了
            if "login" in page.url:
                raise Exception("Cookie 已失效，网页重定向到了登录页。请更新 Secrets 中的 Cookie。")

            # --- 第二步：跳转到具体的续期页面 ---
            if TARGET_URL not in page.url:
                print(f"2️⃣ 跳转到目标页面: {TARGET_URL}")
                page.goto(TARGET_URL, wait_until='networkidle')
            
            page.wait_for_timeout(3000)
            page.screenshot(path="debug_step2_target.png")

            # --- 第三步：寻找并点击页面上的 Renew 按钮 (触发弹窗) ---
            print("3️⃣ 寻找页面上的 Renew 按钮...")
            
            # 尝试多种定位方式
            renew_btn = None
            if page.get_by_text("Renew", exact=True).is_visible():
                renew_btn = page.get_by_text("Renew", exact=True)
            elif page.locator(".btn-primary:has-text('Renew')").is_visible():
                renew_btn = page.locator(".btn-primary:has-text('Renew')")
            
            if renew_btn:
                print("✅ 找到按钮，点击...")
                renew_btn.click()
            else:
                print("⚠️ 未找到明显的 Renew 按钮，可能已经弹窗或 ID 错误。")
            
            page.wait_for_timeout(3000)
            page.screenshot(path="debug_step3_modal.png")

            # --- 第四步：处理 Cloudflare 和 确认续期 ---
            print("4️⃣ 处理弹窗验证...")
            
            # 检测 iframe (Cloudflare 验证码)
            # 你的截图显示验证码在弹窗里
            try:
                # 等待 iframe 出现
                iframe = page.frame_locator("iframe[src*='challenges.cloudflare.com']").first
                if iframe.locator("body").is_visible():
                    print("👀 检测到 Cloudflare 验证框")
                    page.wait_for_timeout(2000)
                    # 尝试点击 checkbox
                    cb = iframe.locator("input[type='checkbox']")
                    if cb.is_visible():
                         print("point_right: 点击验证码 Checkbox...")
                         cb.click()
                         page.wait_for_timeout(3000)
                    else:
                        print("验证码可能已自动通过或不可见")
            except:
                print("未检测到或无需 Cloudflare 验证")

            # --- 第五步：点击弹窗里的蓝色 Renew 按钮 ---
            print("5️⃣ 点击最终确认按钮...")
            
            # 根据你的截图，这是弹窗右下角的蓝色按钮
            # 我们尝试定位弹窗里的按钮
            final_btn = page.locator(".modal-footer button:has-text('Renew')")
            
            if final_btn.is_visible():
                final_btn.click()
                print("✅ 已点击最终 Renew 按钮")
            else:
                # 备用方案：盲点所有可见的 Renew
                print("⚠️ 未精确定位到弹窗按钮，尝试点击页面所有 Renew...")
                page.get_by_role("button", name="Renew").last.click()

            # 等待结果响应
            page.wait_for_timeout(5000)
            page.screenshot(path="debug_step4_result.png")
            
            # 简单判断结果
            content = page.content().lower()
            if "success" in content or "extend" in content:
                msg = f"✅ 脚本执行成功！\n请登录面板确认到期时间。\n(Target: {TARGET_URL})"
            else:
                msg = f"⚠️ 脚本执行完毕，未检测到明确成功标志。\n请查看 GitHub Artifacts 截图确认。\n(Target: {TARGET_URL})"
            
            print(msg)
            send_telegram(msg)

        except Exception as e:
            err_msg = f"❌ 脚本运行出错: {str(e)}"
            print(err_msg)
            try:
                page.screenshot(path="debug_error.png")
            except:
                pass
            send_telegram(err_msg)
            exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    run()
