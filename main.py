import requests
from bs4 import BeautifulSoup
import os
import time
import random

# --- 1. 获取环境变量 (Secrets) ---
COOKIE = os.environ.get("COOKIE")
USER_AGENT = os.environ.get("USER_AGENT")

# 通知配置 (可选)
SCKEY = os.environ.get("SCKEY")
TG_BOT_TOKEN = os.environ.get("TGBOT")
TG_USER_ID = os.environ.get("TGUSERID")

# 您的服务器 ID (从之前的日志确认为 180484)
SERVER_IDS = [180484]

# --- 2. 定义通知函数 ---
def send_notify(msg):
    print(f"准备发送通知: {msg}")
    
    # Telegram 推送
    if TG_BOT_TOKEN and TG_USER_ID:
        try:
            tg_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
            # 增加超时设置，防止卡死
            requests.post(tg_url, data={"chat_id": TG_USER_ID, "text": msg}, timeout=10)
        except Exception as e:
            print(f"Telegram 推送失败: {e}")

    # Server酱 推送
    if SCKEY:
        try:
            sc_url = f"https://sctapi.ftqq.com/{SCKEY}.send"
            requests.post(sc_url, data={"title": "VPS续期通知", "desp": msg}, timeout=10)
        except Exception as e:
            print(f"Server酱 推送失败: {e}")

# --- 3. 核心续期逻辑 ---
def renew(server_id):
    # 检查必要变量是否存在
    if not COOKIE or not USER_AGENT:
        error_msg = "❌ 错误: 缺少必要变量。请检查 GitHub Secrets 中是否填写了 COOKIE 和 USER_AGENT。"
        print(error_msg)
        # 这里不发送通知，因为如果没配置好 Secrets，发通知也会失败
        return

    # 构造高度仿真的请求头 (对抗 Cloudflare)
    headers = {
        "User-Agent": USER_AGENT,
        "Cookie": COOKIE,
        "Referer": "https://dashboard.katabump.com/dashboard",
        "Origin": "https://dashboard.katabump.com",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Cache-Control": "max-age=0",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }
    
    session = requests.Session()
    
    try:
        # 第一步：访问编辑页面，提取隐藏的 CSRF Token
        print(f"正在访问服务器 {server_id} 页面获取 Token...")
        edit_url = f"https://dashboard.katabump.com/servers/edit?id={server_id}"
        
        # 增加超时，防止网络卡死
        resp = session.get(edit_url, headers=headers, timeout=30)
        
        if resp.status_code != 200:
            msg = f"❌ 访问页面失败 (Code {resp.status_code})。Cookie 可能已过期，请重新提取。"
            print(msg)
            send_notify(msg)
            return

        soup = BeautifulSoup(resp.text, 'html.parser')
        # 寻找名为 csrf 的隐藏输入框
        csrf_input = soup.find('input', {'name': 'csrf'})
        
        if not csrf_input:
            msg = "❌ 失败：页面中未找到 CSRF Token。可能登录状态已失效，或者触发了 Cloudflare 验证。"
            print(msg)
            send_notify(msg)
            return
            
        csrf_token = csrf_input.get('value')
        print(f"✅ 成功获取 CSRF Token: {csrf_token[:15]}...")

        # 第二步：发送续期请求
        # 随机等待 2-5 秒，模拟真人操作延迟，降低风控概率
        delay = random.randint(2, 5)
        print(f"等待 {delay} 秒后提交请求...")
        time.sleep(delay)
        
        renew_url = f"https://dashboard.katabump.com/api-client/renew?id={server_id}"
        # 构造表单数据
        payload = {"csrf": csrf_token}
        
        print("🚀 正在提交续期请求...")
        post_resp = session.post(renew_url, headers=headers, data=payload, timeout=30)
        
        if post_resp.status_code == 200:
            print("请求发送完成。")
            # 尝试判断是否真的成功（通常成功后页面会有 success 提示，或者重定向）
            # 注意：KataBump 成功时往往返回 JSON 或者简单的重定向页面
            result_preview = post_resp.text[:100].replace("\n", " ")
            
            success_keywords = ["success", "renew", "redirect", "ok", "true"]
            if any(k in post_resp.text.lower() for k in success_keywords):
                status_msg = "✅ 续期成功 (大概率)"
            else:
                status_msg = "⚠️ 请求已发送 (需人工确认)"
                
            final_msg = f"服务器 {server_id}: {status_msg}\n状态码: 200\n返回摘要: {result_preview}"
            send_notify(final_msg)
        else:
            fail_msg = f"❌ 续期请求失败，状态码: {post_resp.status_code}。\n可能是 Cloudflare 拦截。"
            print(fail_msg)
            send_notify(fail_msg)

    except requests.exceptions.RequestException as e:
        err_msg = f"❌ 网络请求出错: {e}"
        print(err_msg)
        send_notify(err_msg)
    except Exception as e:
        err_msg = f"❌ 脚本执行出错: {e}"
        print(err_msg)
        send_notify(err_msg)

if __name__ == "__main__":
    print("="*30)
    print("开始运行 KataBump 自动续期脚本")
    print(f"当前时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*30)
    
    for sid in SERVER_IDS:
        renew(sid)
        
    print("="*30)
    print("所有任务执行完毕。")
