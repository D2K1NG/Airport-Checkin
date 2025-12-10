import requests
from bs4 import BeautifulSoup
import os
import time
import random

# --- 1. 获取配置 ---
COOKIE = os.environ.get("COOKIE")
USER_AGENT = os.environ.get("USER_AGENT")
SCKEY = os.environ.get("SCKEY")
TG_BOT_TOKEN = os.environ.get("TGBOT")
TG_USER_ID = os.environ.get("TGUSERID")

SERVER_IDS = [180484]

# --- 2. 通知函数 ---
def send_notify(msg):
    print(f"🔔 通知: {msg}")
    if TG_BOT_TOKEN and TG_USER_ID:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage", 
                          data={"chat_id": TG_USER_ID, "text": msg}, timeout=10)
        except: pass
    if SCKEY:
        try:
            requests.post(f"https://sctapi.ftqq.com/{SCKEY}.send", 
                          data={"title": "VPS续期通知", "desp": msg}, timeout=10)
        except: pass

# --- 3. 核心逻辑 ---
def renew(server_id):
    if not COOKIE or not USER_AGENT:
        print("❌ 错误: Secrets 中缺少 COOKIE 或 USER_AGENT")
        return

    # ⚡⚡⚡ 针对性优化的请求头 (完全模仿你的 Edge 浏览器) ⚡⚡⚡
    headers = {
        "User-Agent": USER_AGENT,
        "Cookie": COOKIE,
        "Referer": "https://dashboard.katabump.com/dashboard",
        "Origin": "https://dashboard.katabump.com",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Cache-Control": "max-age=0",
        "Priority": "u=0, i",
        # 下面这几行是 Cloudflare 检查的重点
        "Sec-Ch-Ua": '"Microsoft Edge";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }
    
    session = requests.Session()
    
    try:
        # 1. 获取 CSRF
        print(f"☁️ 正在连接服务器 {server_id} 获取令牌...")
        edit_url = f"https://dashboard.katabump.com/servers/edit?id={server_id}"
        resp = session.get(edit_url, headers=headers, timeout=25)
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        page_title = soup.title.string.strip() if soup.title else "无标题"
        
        # 检查是否被拦截
        if "Just a moment" in page_title or "Cloudflare" in resp.text:
            msg = f"❌ 失败: 被 Cloudflare 盾拦截。\n原因: IP变动导致 Cookie 失效。\n建议: 只能在本地电脑运行脚本。"
            print(msg)
            send_notify(msg)
            return
            
        csrf_input = soup.find('input', {'name': 'csrf'})
        if not csrf_input:
            msg = f"❌ 失败: 页面载入但未找到 Token。\n页面标题: {page_title}\n可能是登录状态已过期。"
            print(msg)
            send_notify(msg)
            return
            
        csrf_token = csrf_input.get('value')
        print(f"✅ 成功获取 Token: {csrf_token[:10]}...")

        # 2. 提交续期
        time.sleep(random.randint(2, 4)) # 模拟真人延迟
        renew_url = f"https://dashboard.katabump.com/api-client/renew?id={server_id}"
        
        print("🚀 发送续期请求...")
        post_resp = session.post(renew_url, headers=headers, data={"csrf": csrf_token}, timeout=25)
        
        if post_resp.status_code == 200:
            success_msg = f"✅ 服务器 {server_id} 续期请求已送达 (200 OK)。\n请登录面板确认有效期。"
            print(success_msg)
            send_notify(success_msg)
        else:
            fail_msg = f"❌ 续期请求被拒绝 (Code {post_resp.status_code})。"
            print(fail_msg)
            send_notify(fail_msg)

    except Exception as e:
        err = f"❌ 脚本运行出错: {e}"
        print(err)
        send_notify(err)

if __name__ == "__main__":
    for sid in SERVER_IDS:
        renew(sid)
