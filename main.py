import os
import time
import random
import requests
from playwright.sync_api import sync_playwright

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
    payload = {"chat_id": TG_USER_ID, "text": f"🤖 VPS续期通知 (V8):\n{msg}", "parse_mode": "Markdown"}
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

def human_move(page, x=None, y=None):
    """模拟更真实的人类鼠标移动"""
    try:
        # 如果没有指定目标，就随机动一下
        target_x = x if x else random.randint(100, 1000)
        target_y = y if y else random.randint(100, 800)
        page.mouse.move(target_x, target_y, steps=random.randint(5, 15))
        time.sleep(random.uniform(0.2, 0.5))
    except:
        pass

def run():
    print("🚀 启动 V8 原生隐身版...")
    
    if not COOKIE_STR or not TARGET_URL:
        send_telegram("❌ 致命错误：Secrets 变量缺失")
        exit(1)

    final_ua = USER_AGENT if USER_AGENT else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    try:
        domain = TARGET_URL.split("/")[2]
    except:
        domain = "dashboard.katabump.com"

    with sync_playwright() as p:
        # 启动浏览器，移除所有自动化标记
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled', 
                '--no-sandbox',
                '--disable-infobars',
            ]
        )
        
        context = browser.new_context(
            user_agent=final_ua,
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
        )
        
        context.add_cookies(parse_cookies(COOKIE_STR, domain))
        page = context.new_page()

        # 🔥 核心修正：使用 add_init_script 手动注入隐身代码
        # 这段代码会在页面加载前执行，彻底抹除机器人特征
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.navigator.chrome = {
                runtime: {},
            };
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3],
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en'],
            });
        """)
        
        page.set_default_timeout(90000)

        try:
            # 1. 访问页面
            print(f"1️⃣ 进入页面: {TARGET_URL}")
            page.goto(TARGET_URL, wait_until='domcontentloaded')
            human_move(page)
            page.wait_for_timeout(3000)

            if "login" in page.url:
                raise Exception("Cookie失效，重定向回登录页")

            # 2. 触发弹窗
            print("2️⃣ 点击 Renew 按钮...")
            # 尝试点击页面中间的 Renew
            clicked = False
            try:
                page.get_by_text("Renew", exact=True).first.click()
                clicked = True
            except:
                # 备用：点击 CSS 类
                try:
                    page.locator(".btn-primary").filter(has_text="Renew").click()
                    clicked = True
                except:
                    pass
            
            if not clicked:
                print("⚠️ 未找到主界面按钮，可能已在弹窗中")

            page.wait_for_timeout(3000)
            page.screenshot(path="step2_modal.png")

            # 3. 对抗 Cloudflare (死循环等待验证成功)
            print("3️⃣ 处理 Cloudflare (等待变绿)...")
            captcha_passed = False
            
            try:
                iframe = page.frame_locator("iframe[src*='challenges.cloudflare.com']").first
                # 等待 iframe 加载
                iframe.locator("body").wait_for(timeout=8000)
                
                cb = iframe.locator("input[type='checkbox']")
                if cb.is_visible():
                    print("👀 发现验证码，模拟鼠标操作...")
                    # 获取复选框位置
                    box = cb.bounding_box()
                    if box:
                        # 移动鼠标到复选框中心
                        human_move(page, box["x"] + 15, box["y"] + 15)
                        page.mouse.down()
                        time.sleep(0.2)
                        page.mouse.up()
                    else:
                        cb.click(force=True)
                    
                    print("⏳ 点击完毕，死等 'Success' 信号...")
                    # 轮询 20 次，每次 1 秒
                    for i in range(20):
                        # 你的成功截图里有 "Success!" 或 "成功"
                        if iframe.get_by_text("Success").is_visible() or iframe.get_by_text("成功").is_visible():
                            print("✅ 验证码变绿！(Verified)")
                            captcha_passed = True
                            break
                        time.sleep(1)
                    
                    if not captcha_passed:
                        print("❌ 超时：验证码一直未变绿 (可能是 IP 黑名单)")
                        # 截图留证
                        page.screenshot(path="step3_captcha_failed.png")
                else:
                    print("验证码不可见，假设已自动通过")
                    captcha_passed = True

            except Exception as e:
                print(f"CF 处理跳过 (无验证码?): {str(e)[:50]}")
                captcha_passed = True # 没找到验证码就当是通过了

            # 4. 只有验证通过才点击最终按钮
            if captcha_passed:
                print("4️⃣ 点击最终 Renew...")
                page.wait_for_timeout(2000)
                
                # 再次确认是否有红色报错条，如果有，说明之前状态不对，刷新没用，只能硬点
                if page.locator(".alert-danger").is_visible():
                    print("⚠️ 警告：页面已存在报错条")

                # JS 穿透点击
                js_script = """
                    const btns = Array.from(document.querySelectorAll('.modal-dialog button'));
                    const target = btns.find(b => b.innerText.includes('Renew'));
                    if(target) { target.click(); return true; }
                    return false;
                """
                if not page.evaluate(js_script):
                    # 备用：点击最后一个 Renew
                    btns = page.get_by_role("button", name="Renew").all()
                    if btns:
                        btns[-1].click()
                
                print("✅ 最终按钮已点击")
            else:
                print("⛔ 验证未通过，跳过最终点击，防止报错")

            # 5. 结果检查
            print("5️⃣ 等待服务器响应...")
            page.wait_for_timeout(8000)
            page.screenshot(path="step5_final.png")

            content = page.content().lower()
            if "success" in content or "extended" in content:
                msg = "✅ V8 续期成功！"
            elif "captcha" in content or not captcha_passed:
                msg = "❌ 失败：Cloudflare 验证拦截 (GitHub IP 被风控)。"
            else:
                msg = "⚠️ 脚本结束，未检测到成功标志，请查看截图。"

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
