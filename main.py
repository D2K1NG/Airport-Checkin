import os
import time
import random
import requests
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync # 引入隐身模块

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
    payload = {"chat_id": TG_USER_ID, "text": f"🤖 VPS续期通知 (V6):\n{msg}", "parse_mode": "Markdown"}
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
            cookies.append({'name': name.strip(), 'value': value.strip(), 'domain': domain, 'path': '/'})
    return cookies

def human_move(page):
    """模拟人类鼠标随机移动"""
    try:
        for _ in range(3):
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            page.mouse.move(x, y, steps=10)
            time.sleep(random.uniform(0.1, 0.5))
    except:
        pass

def run():
    print("🚀 启动 V6 隐身抗检测版...")
    
    if not COOKIE_STR or not TARGET_URL:
        send_telegram("❌ 缺变量")
        exit(1)

    final_ua = USER_AGENT if USER_AGENT else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    try:
        domain = TARGET_URL.split("/")[2]
    except:
        domain = "dashboard.katabump.com"

    with sync_playwright() as p:
        # 添加更多启动参数来禁用自动化特征
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-infobars',
                '--disable-dev-shm-usage',
                '--disable-browser-side-navigation',
                '--disable-gpu'
            ]
        )
        
        context = browser.new_context(
            user_agent=final_ua,
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
            timezone_id='Asia/Shanghai' # 尝试伪装时区
        )
        
        context.add_cookies(parse_cookies(COOKIE_STR, domain))
        page = context.new_page()
        
        # 🔥 关键：开启隐身模式
        stealth_sync(page)
        
        page.set_default_timeout(60000)

        try:
            # 1. 访问管理页
            print(f"1️⃣ 进入页面: {TARGET_URL}")
            page.goto(TARGET_URL, wait_until='domcontentloaded')
            human_move(page) # 动动鼠标
            page.wait_for_timeout(3000)

            if "login" in page.url:
                raise Exception("Cookie失效，重定向回登录页")

            # 2. 触发弹窗
            print("2️⃣ 点击 Renew 按钮...")
            # 优先点页面中间那个大按钮 (如果有)
            clicked = False
            try:
                page.get_by_text("Renew", exact=True).first.click()
                clicked = True
            except:
                # 尝试 CSS 定位
                btn = page.locator(".btn-primary").filter(has_text="Renew")
                if btn.count() > 0:
                    btn.first.click()
                    clicked = True
            
            if not clicked:
                print("⚠️ 未找到 Renew 按钮，可能已在弹窗中")
            
            page.wait_for_timeout(3000)
            page.screenshot(path="step2_modal.png")

            # 3. 对抗 Cloudflare
            print("3️⃣ 智能处理 Cloudflare...")
            
            iframe = None
            try:
                iframe = page.frame_locator("iframe[src*='challenges.cloudflare.com']").first
                # 等待 iframe 出现
                iframe.locator("body").wait_for(timeout=5000)
                
                # 检查 Checkbox
                cb = iframe.locator("input[type='checkbox']")
                if cb.is_visible():
                    print("👀 发现验证码，模拟人类操作...")
                    human_move(page) # 鼠标晃过去
                    time.sleep(0.5)
                    # 尝试点击 Checkbox 的中心位置，而不是直接 click()
                    box = cb.bounding_box()
                    if box:
                        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    else:
                        cb.click(force=True)
                    
                    print("👆 已点击验证码，等待变绿...")
                    
                    # 轮询检查成功标志
                    passed = False
                    for _ in range(20): # 等待 20秒
                        # 检查是否有 "Success" 或 "成功"
                        if iframe.get_by_text("Success").is_visible() or iframe.get_by_text("成功").is_visible():
                            print("✅ 验证码通过！")
                            passed = True
                            break
                        time.sleep(1)
                    
                    if not passed:
                        print("⚠️ 验证码未变绿 (可能是 IP 黑名单)，强行尝试下一步...")
                else:
                    print("验证码 Checkbox 不可见 (可能已自动通过)")

            except Exception as e:
                print(f"CF 处理跳过: {str(e)[:50]}")

            page.wait_for_timeout(2000)

            # 4. 点击最终确认
            print("4️⃣ 点击最终 Renew...")
            human_move(page)
            
            # 使用 JS 点击，确保命中
            js_script = """
                const btns = Array.from(document.querySelectorAll('.modal-dialog button'));
                const target = btns.find(b => b.innerText.includes('Renew'));
                if(target) { target.click(); return true; }
                return false;
            """
            if not page.evaluate(js_script):
                # 备用：暴力点击所有可见的 Renew
                btns = page.get_by_role("button", name="Renew").all()
                for btn in btns:
                    if btn.is_visible():
                        btn.click()
            
            print("✅ 点击动作已执行，等待服务器响应...")
            page.wait_for_timeout(8000) # 多等一会
            page.screenshot(path="step4_final.png")

            # 5. 结果判定
            content = page.content().lower()
            if "success" in content or "extended" in content:
                msg = "✅ V6 续期成功！(Success/Extended)"
            elif "captcha" in content:
                msg = "❌ 失败：Cloudflare 验证码拦截 (IP 风控)。"
            else:
                msg = "⚠️ 脚本结束，结果未知，请查看截图 step4_final.png"

            print(msg)
            send_telegram(msg)

        except Exception as e:
            err = f"❌ 运行报错: {str(e)}"
            print(err)
            send_telegram(err)
            try:
                page.screenshot(path="error.png")
            except: pass
        finally:
            browser.close()

if __name__ == "__main__":
    run()
