import os
import time
import requests
from playwright.sync_api import sync_playwright

# --- 环境变量 ---
COOKIE_STR = os.environ.get("COOKIE")
TARGET_URL = os.environ.get("URL") # 例如 https://dashboard.katabump.com/servers/edit?id=xxxx
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_USER_ID = os.environ.get("TG_USER_ID")

def send_telegram(msg):
    """发送 TG 通知"""
    if not TG_TOKEN or not TG_USER_ID: return
    print(f"准备发送通知: {msg}")
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_USER_ID, "text": f"🤖 VPS续期通知:\n{msg}", "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def parse_cookies(cookie_str, domain):
    """将 Cookie 字符串转换为 Playwright 可用的字典列表"""
    cookies = []
    if not cookie_str: return cookies
    for item in cookie_str.split(';'):
        if '=' in item:
            name, value = item.strip().split('=', 1)
            cookies.append({
                'name': name,
                'value': value,
                'domain': domain,
                'path': '/'
            })
    return cookies

def run():
    if not COOKIE_STR or not TARGET_URL:
        print("❌ 缺少环境变量 COOKIE 或 URL")
        exit(1)

    # 提取域名用于设置 Cookie
    domain = TARGET_URL.split("/")[2] 

    with sync_playwright() as p:
        # 启动浏览器，尝试添加参数以隐藏自动化特征
        browser = p.chromium.launch(
            headless=True, # GitHub Actions 必须用 headless，但在本地调试可用 False
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
        )
        
        # 创建上下文，设置 UserAgent 为常见浏览器
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720}
        )
        
        # 注入 Cookies
        context.add_cookies(parse_cookies(COOKIE_STR, domain))
        
        page = context.new_page()
        
        try:
            print(f"1️⃣ 正在访问: {TARGET_URL}")
            page.goto(TARGET_URL, timeout=60000)
            page.wait_for_load_state("networkidle")
            
            # 截图调试 1
            print("📸 页面加载完成，保存截图 page_loaded.png")
            page.screenshot(path="page_loaded.png")

            # 检查是否还是登录页（Cookie 是否有效）
            if "login" in page.url:
                raise Exception("Cookie 失效，重定向到了登录页")

            # --- 寻找并点击“Renew”按钮打开弹窗 ---
            # 根据你之前的截图，如果你已经在 edit 页面，可能需要点击页面上的某个 Renew 按钮
            # 假设页面上有一个文本为 Renew 的按钮或者链接
            print("2️⃣ 寻找 Renew 按钮...")
            # 尝试点击页面上可见的 Renew 按钮 (根据之前的 HTML 分析)
            # 这里使用模糊匹配，匹配内容包含 Renew 的按钮或链接
            try:
                # 优先找那个红色的或者显眼的 Renew 按钮
                # 如果 URL 直接带出了弹窗（如你截图所示），这一步可能不需要
                # 但为了保险，尝试找一下。
                page.click('text=Renew', timeout=5000)
            except:
                print("⚠️ 没找到主界面的 Renew 按钮，假设弹窗已经自动弹出或需要手动触发...")

            # --- 处理 Cloudflare 验证码 ---
            # 你的截图显示验证码在弹窗里。
            print("3️⃣ 等待 Cloudflare 验证...")
            time.sleep(5) # 给它一点时间加载 iframe

            # 寻找 Cloudflare iframe
            # Cloudflare 通常在一个 iframe 里，title 通常包含 "Widget containing a Cloudflare security challenge"
            # 我们尝试等待那个绿色的勾出现，或者尝试点击
            
            # 这一步是玄学，GitHub Actions IP 可能会让它一直转圈
            try:
                # 寻找 iframe
                iframe_element = page.frame_locator("iframe[src*='challenges.cloudflare.com']")
                
                # 尝试点击 checkbox (如果存在)
                checkbox = iframe_element.locator("input[type='checkbox']")
                if checkbox.is_visible():
                    print("Found Cloudflare checkbox, clicking...")
                    checkbox.click()
                    time.sleep(2)
                
                # 等待验证成功标志 (截图里的 "成功!" 或者 "Success")
                # 或者直接等待下面的那个蓝色的 "Renew" 按钮变亮/可点击
                
            except Exception as e:
                print(f"Cloudflare 处理异常 (可忽略): {e}")

            # 截图调试 2
            print("📸 验证后截图 check_captcha.png")
            page.screenshot(path="check_captcha.png")

            # --- 点击弹窗里的最终 Renew ---
            print("4️⃣ 尝试点击弹窗里的确认 Renew 按钮...")
            
            # 也就是截图里那个蓝色的 Renew 按钮
            # 定位方式：模态框里的蓝色按钮
            # 尝试通过 CSS 类名或文本定位
            
            # 强行等待一会，确保验证通过
            time.sleep(5)
            
            # 点击!
            page.click('button:has-text("Renew")', timeout=10000)
            
            print("✅ 点击完成，等待响应...")
            time.sleep(5)
            
            # 截图调试 3
            print("📸 最终结果截图 result.png")
            page.screenshot(path="result.png")
            
            # 判断成功依据：页面是否提示 Success，或者 URL 变了，或者弹窗消失
            content = page.content()
            if "success" in content.lower() or "extended" in content.lower():
                msg = "✅ 脚本执行完毕，检测到成功关键词，请登录验证。"
            else:
                msg = "⚠️ 脚本执行完毕，未检测到明确成功标志，请查看截图或登录验证。"
            
            print(msg)
            send_telegram(msg)

        except Exception as e:
            err_msg = f"❌ 脚本执行出错: {str(e)}"
            print(err_msg)
            # 出错时截图
            try:
                page.screenshot(path="error.png")
            except:
                pass
            send_telegram(err_msg)
        finally:
            # 上传截图到 GitHub Artifacts 方便你调试查看
            # (这一步需要 workflow yaml 支持，暂时先只做本地保存，但在 Actions 里看不到)
            # 为了让你看到截图，我需要在 yaml 里加一步 upload-artifact
            browser.close()

if __name__ == "__main__":
    run()
