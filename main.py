import requests
from bs4 import BeautifulSoup
import os
import time

# --- 配置区域 (从 GitHub Secrets 获取) ---
# 注意：KataBump 这类面板不能只用账号密码登录，必须用 Cookie 绕过 Cloudflare
COOKIE = os.environ.get("COOKIE")
USER_AGENT = os.environ.get("USER_AGENT")

# 你的服务器 ID，从你提供的 URL 或 HTML 中可以看到是 180484
# 如果你有多个服务器，可以把 IDs 写成列表，例如 [180484, 123456]
SERVER_IDS = [180484] 

# 推送配置 (Server酱 / TG)
SCKEY = os.environ.get("SCKEY")
TG_BOT_TOKEN = os.environ.get("TGBOT")
TG_USER_ID = os.environ.get("TGUSERID")

def send_notification(content):
    if TG_BOT_TOKEN and TG_USER_ID:
        requests.post(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage", data={"chat_id": TG_USER_ID, "text": content})
    if SCKEY:
        requests.post(f"https://sctapi.ftqq.com/{SCKEY}.send", data={"title": "KataBump续期通知", "desp": content})
    print(f"通知已发送: {content}")

def renew_server(server_id):
    if not COOKIE or not USER_AGENT:
        print("错误：未设置 COOKIE 或 USER_AGENT")
        return

    session = requests.Session()
    headers = {
        "User-Agent": USER_AGENT,
        "Cookie": COOKIE,
        "Referer": "https://dashboard.katabump.com/dashboard",
        "Origin": "https://dashboard.katabump.com"
    }
    
    # 第一步：访问页面获取 CSRF Token
    edit_url = f"https://dashboard.katabump.com/servers/edit?id={server_id}"
    print(f"正在访问页面获取 Token: {edit_url}")
    
    try:
        resp = session.get(edit_url, headers=headers)
        if resp.status_code != 200:
            msg = f"访问页面失败，状态码: {resp.status_code}。可能 Cookie 已过期或被 Cloudflare 拦截。"
            print(msg)
            send_notification(msg)
            return

        # 解析 HTML 寻找 CSRF
        soup = BeautifulSoup(resp.text, 'html.parser')
        # 在 HTML 中寻找 <input type="hidden" name="csrf" value="...">
        csrf_input = soup.find('input', {'name': 'csrf'})
        
        if not csrf_input:
            print("警告：未找到 CSRF Token，尝试直接请求...")
            csrf_token = ""
        else:
            csrf_token = csrf_input.get('value')
            print(f"成功获取 CSRF Token: {csrf_token[:10]}...")

        # 第二步：发送续期请求
        renew_url = f"https://dashboard.katabump.com/api-client/renew?id={server_id}"
        
        # 构造 POST 数据
        # 注意：这里我们无法生成 cf-turnstile-response，只能留空或不传
        # 如果服务器强制校验 Turnstile，这一步会失败 (403 或 500)
        payload = {
            "csrf": csrf_token,
            # "cf-turnstile-response": "" # 无法生成
        }
        
        print("正在发送续期请求...")
        post_resp = session.post(renew_url, headers=headers, data=payload)
        
        if post_resp.status_code == 200:
            # 即使状态码是 200，也要检查返回内容是否包含成功提示
            # 通常成功会重定向或者返回 JSON
            print(f"请求发送成功。服务器返回: {post_resp.text[:100]}")
            send_notification(f"服务器 {server_id} 续期操作已执行。请手动检查是否成功。\n返回: {post_resp.text[:50]}")
        else:
            msg = f"续期失败，状态码: {post_resp.status_code}。可能是 Cloudflare 验证码拦截。"
            print(msg)
            send_notification(msg)

    except Exception as e:
        print(f"发生异常: {e}")
        send_notification(f"脚本执行出错: {e}")

if __name__ == "__main__":
    for sid in SERVER_IDS:
        renew_server(sid)
        time.sleep(5) # 稍微等待一下
