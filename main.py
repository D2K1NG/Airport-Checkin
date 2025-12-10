import requests
import json
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
import time

requests.packages.urllib3.disable_warnings()

# 从环境变量中获取 SCKEY、TG_BOT_TOKEN、TG_USER_ID 等
SCKEY = os.environ.get('SCKEY')
TG_BOT_TOKEN = os.environ.get('TG_BOT_TOKEN')
TG_USER_ID = os.environ.get('TG_USER_ID')

# 配置 Selenium WebDriver，使用无头模式
chrome_options = Options()
chrome_options.add_argument("--headless")  # 开启无头模式
chrome_options.add_argument("--disable-gpu")  # 禁用 GPU 加速
chrome_options.add_argument("--no-sandbox")  # 禁用沙盒模式

driver = webdriver.Chrome(options=chrome_options)

# 打开目标网页
driver.get('https://dashboard.katabump.com/servers/edit?id=180484')  # 替换为你的页面URL

# 等待页面加载
time.sleep(5)

# 查找并点击“Renew”按钮
renew_button = driver.find_element(By.CSS_SELECTOR, 'button[data-bs-toggle="modal"][data-bs-target="#renew-modal"]')

# 使用 ActionChains 来点击按钮
ActionChains(driver).move_to_element(renew_button).click().perform()

# 可以继续操作，比如签到等
time.sleep(2)  # 等待按钮点击后的响应

# 在这里可以继续用 requests 或其他方式进行后续操作
def checkin(email=os.environ.get('EMAIL'), password=os.environ.get('PASSWORD'),
            base_url=os.environ.get('BASE_URL')):
    # 检查 email 格式是否有效
    if not email or '@' not in email:
        print("Invalid email format")
        return "Invalid email format"
    
    email = email.split('@')
    email = email[0] + '%40' + email[1]
    
    session = requests.session()
    session.get(base_url, verify=False)
    
    # 登录请求
    login_url = base_url + '/auth/login'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/56.0.2924.87 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    }
    
    post_data = f'email={email}&passwd={password}&code='
    post_data = post_data.encode()
    response = session.post(login_url, post_data, headers=headers, verify=False)
    
    # 签到请求
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/56.0.2924.87 Safari/537.36',
        'Referer': base_url + '/user'
    }
    
    response = session.post(base_url + '/user/checkin', headers=headers, verify=False)
    try:
        response = json.loads(response.text)
        print(response['msg'])
        return response['msg']
    except json.JSONDecodeError:
        print("Failed to decode response")
        return "Failed to decode response"

# 执行签到操作
result = checkin()

# 通过 Server 酱发送通知
if SCKEY != '':
    sendurl = f'https://sctapi.ftqq.com/{SCKEY}.send?title=机场签到&desp={result}'
    r = requests.get(url=sendurl)

# 通过 Telegram 发送通知
if TG_USER_ID != '':
    sendurl = f'https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage?chat_id={TG_USER_ID}&text={result}&disable_web_page_preview=True'
    r = requests.get(url=sendurl)

# 关闭浏览器
driver.quit()
