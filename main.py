import os
import time
import requests
import random
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# --- 环境变量获取 ---
COOKIE_STR = os.environ.get("COOKIE")
TARGET_URL = os.environ.get("URL") 
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_USER_ID = os.environ.get("TG_USER_ID")
USER_AGENT = os.environ.get("USER_AGENT")

def send_telegram(msg):
    """发送 Telegram 通知"""
    print(f"🔔 准备发送通知: {msg}")
    if not TG_TOKEN or not TG_USER_ID: return
    
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_USER_ID,
        "text": f"🤖 **VPS续期助手**\n\n{msg}",
        "parse_mode": "Markdown"
    }
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
            cookies.append({
                'name': name.strip(),
                'value': value.strip(),
                'domain': domain,
                'path': '/'
            })
    return cookies

def run():
    print("🚀 脚本开始运行 (宽松模式)...")
    
    if not COOKIE_STR or not TARGET_URL:
        send_telegram("❌ 错误：Secrets 缺少 COOKIE 或 URL")
        exit(1)

    # 默认 UA
    final_ua = USER_AGENT if USER_AGENT else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    try:
        domain = TARGET_URL.split("/")[2]
    except:
        domain = "dashboard.katabump.com"

    with sync_playwright() as p:
        print("🌐 启动浏览器...")
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        context = browser.new_context(
            user_agent=final_ua,
            viewport={'width': 1920, 'height': 1080}
        )
        
        context.add_cookies(parse_cookies(COOKIE_STR, domain))
        page = context.new_page()
        # 设置全局超时为 60秒
        page.set_default_timeout(60000) 

        try:
            # --- 第一步：访问主页 (Dashboard) ---
            dashboard_url = f"https://{domain}/dashboard"
            print(f"1️⃣ 访问主页: {dashboard_url}")
            
            # 修改点：使用 domcontentloaded，不等待网络空闲
            try:
                page.goto(dashboard_url, wait_until='domcontentloaded', timeout=30000)
            except Exception as e:
                print(f"⚠️ 主页加载轻微超时，尝试继续... ({str(e)[:50]})")

            page.wait_for_timeout(3000)
            
            # 检查是否到了登录页
            if "login" in page.url:
                page.screenshot(path="error_login.png")
                raise Exception("Cookie失效，已跳转回登录页")

            # --- 第二步：跳转到续期页 ---
            print(f"2️⃣ 跳转目标页: {TARGET_URL}")
            try:
                # 修改点：这里最容易超时，改用最宽松的等待策略
                page.goto(TARGET_URL, wait_until='domcontentloaded', timeout=45000)
            except Exception as e:
                print(f"⚠️ 目标页加载未完全结束 (超时)，尝试强行寻找按钮... ({str(e)[:50]})")
            
            # 强制等待几秒让 JS 跑一会儿
            page.wait_for_timeout(5000)
            page.screenshot(path="debug_target_loaded.png")

            # --- 第三步：寻找 Renew 按钮 ---
            print("3️⃣ 尝试定位 Renew 按钮...")
            
            renew_btn = None
            # 尝试显式等待按钮出现
            try:
                # 寻找包含 Renew 文本的任意元素
                if page.locator("text=Renew").count() > 0:
                    renew_btn = page.locator("text=Renew").first
                elif page.locator(".btn-primary").count() > 0:
                    renew_btn = page.locator(".btn-primary").first
            except:
                pass

            if renew_btn:
                print("✅ 找到按钮，点击...")
                # 强制点击，忽略遮挡
                renew_btn.click(force=True) 
            else:
                print("⚠️ 未找到按钮，可能已自动弹出验证框？")

            page.wait_for_timeout(3000)

            # --- 第四步：Cloudflare 验证处理 ---
            print("4️⃣ 检查 Cloudflare...")
            try:
                # 查找 iframe
                iframe = page.frame_locator("iframe[src*='challenges.cloudflare.com']").first
                if iframe.locator("input[type='checkbox']").is_visible():
                    print("👆 点击 Cloudflare 复选框...")
                    iframe.locator("input[type='checkbox']").click(force=True)
                    page.wait_for_timeout(3000)
            except:
                pass

            # --- 第五步：确认续期 ---
            print("5️⃣ 点击确认...")
            try:
                # 尝试点击模态框里的 Renew
                page.locator(".modal-footer button").last.click(timeout=5000)
            except:
                # 备选：点击页面上所有看起来像按钮的东西
                try:
                    page.get_by_role("button", name="Renew").click(timeout=5000)
                except:
                    pass

            page.wait_for_timeout(5000)
            page.screenshot(path="result.png")
            
            # 最终判断
            if "success" in page.content().lower() or "extend" in page.content().lower():
                msg = "✅ 脚本执行成功！(检测到 success 关键词)"
            else:
                msg = "⚠️ 脚本执行完毕，请检查截图确认结果。"
            
            print(msg)
            send_telegram(msg)

        except Exception as e:
            err = f"❌ 运行报错: {str(e)}"
            print(err)
            try:
                page.screenshot(path="crash.png")
            except:
                pass
            send_telegram(err)
            exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    run()
