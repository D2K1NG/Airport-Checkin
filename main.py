import time
import random
import os
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ================= 配置区域 =================
TARGET_URL = os.environ.get("URL")
COOKIE_STR = os.environ.get("COOKIE")
TGBOT = os.environ.get("TGBOT")
TG_USER = os.environ.get("TGUSERID")
# ===========================================

def send_tg(msg):
    if TGBOT and TG_USER:
        try:
            requests.post(f"https://api.telegram.org/bot{TGBOT}/sendMessage", 
                          json={"chat_id": TG_USER, "text": msg, "parse_mode": "HTML"}, timeout=5)
        except Exception as e:
            print(f"TG 推送失败: {e}")

def parse_cookie_string(raw_str):
    """解析 Cookie 字符串为 Selenium 格式"""
    if not raw_str: return []
    cookies = []
    items = raw_str.split(';')
    for item in items:
        if '=' in item:
            try:
                name, value = item.strip().split('=', 1)
                cookies.append({
                    'name': name,
                    'value': value,
                    'domain': 'dashboard.katabump.com', # 必须指定域名，否则 Selenium 会报错
                    'path': '/'
                })
            except: continue
    return cookies

def human_type_keys(driver, keys_list):
    """
    🤖 拟人化按键：Selenium 版本
    """
    actions = ActionChains(driver)
    for key in keys_list:
        delay = random.uniform(0.1, 0.3)
        print(f"⌨️ 按下 {key} (延迟 {delay:.2f}s)...")
        actions.send_keys(key)
        actions.pause(delay)
    actions.perform()

def run():
    print("🚀 启动 (undetected_chromedriver 模式)...")
    
    # 确保截图目录存在
    os.makedirs("debug_screenshots", exist_ok=True)

    if not TARGET_URL or not COOKIE_STR:
        print("❌ 错误：环境变量未设置")
        return

    # 配置 Chrome 选项
    options = uc.ChromeOptions()
    options.add_argument("--no-first-run")
    options.add_argument("--no-service-autorun")
    options.add_argument("--password-store=basic")
    # ⚠️ 绝对不要开启 --headless，这是被 CF 检测的主要原因
    # 我们将在 GitHub Actions 中使用 xvfb 来提供虚拟显示环境

    try:
        # 启动浏览器 (use_subprocess=True 可提高稳定性)
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=None)
        driver.set_window_size(1920, 1080)
        
        print(f"👉 预访问域名以植入 Cookie...")
        # Selenium 必须先访问域名才能设置 Cookie
        try:
            # 先访问登录页或主页，允许失败（可能遇到 CF 盾），主要为了定域
            driver.get("https://dashboard.katabump.com/login")
            time.sleep(3)
        except: pass

        # 植入 Cookie
        print("🍪 正在植入 Cookies...")
        cookies = parse_cookie_string(COOKIE_STR)
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                print(f"⚠️ Cookie 设置警告: {e}")

        # 正式访问目标页面
        print(f"👉 正式访问: {TARGET_URL}")
        driver.get(TARGET_URL)
        
        # 截图调试 1
        driver.save_screenshot("debug_screenshots/1_page_loaded.png")
        time.sleep(5)

        # 检查是否登录成功（检查 email 输入框是否存在，存在则说明没登录）
        if "login" in driver.current_url or len(driver.find_elements(By.NAME, "email")) > 0:
            print("❌ Cookie 失效或遇到 CF 拦截")
            driver.save_screenshot("debug_screenshots/login_failed.png")
            send_tg("❌ 机场签到失败：Cookie 失效或被 CF 拦截")
            return

        # 查找 Renew 按钮
        # 尝试多种定位方式
        renew_btns = driver.find_elements(By.XPATH, "//*[contains(text(), 'Renew')]")
        if not renew_btns:
            renew_btns = driver.find_elements(By.CSS_SELECTOR, '[data-bs-target="#renew-modal"]')
        
        if renew_btns:
            print("🖱️ 找到 Renew 按钮，准备点击...")
            # 滚动到按钮处
            driver.execute_script("arguments[0].scrollIntoView();", renew_btns[0])
            time.sleep(1)
            try:
                renew_btns[0].click()
            except:
                driver.execute_script("arguments[0].click();", renew_btns[0])

            # ==========================================
            # 👇 严格遵守你的 15秒 + Tab 流程
            # ==========================================
            print("⏳ (1/3) 严格等待 15 秒...")
            time.sleep(15)

            # 尝试点击 Modal 文本区域以获取焦点
            print("🔒 点击弹窗区域锁定焦点...")
            try:
                modal_body = driver.find_element(By.CSS_SELECTOR, "#renew-modal .modal-body")
                modal_body.click()
            except:
                # 如果找不到具体 body，点击页面中心
                ActionChains(driver).move_by_offset(960, 540).click().perform()
            
            time.sleep(1)

            print("⌨️ 执行键盘流: Tab x2 -> Space")
            
            actions = ActionChains(driver)
            
            # Tab 1
            actions.send_keys(Keys.TAB).pause(random.uniform(0.8, 1.5))
            # Tab 2
            actions.send_keys(Keys.TAB).pause(random.uniform(0.8, 1.5))
            # Space
            actions.send_keys(Keys.SPACE)
            
            print("▶️ 发送按键指令...")
            actions.perform()

            print("⏳ 验证码动作完成，等待 6 秒...")
            time.sleep(6)
            driver.save_screenshot("debug_screenshots/2_after_captcha.png")
            # ==========================================

            # 提交 Renew
            print("🚀 提交 Renew...")
            try:
                confirm_btn = driver.find_element(By.CSS_SELECTOR, "#renew-modal button.btn-primary")
                confirm_btn.click()
            except:
                print("⚠️ 找不到确认按钮，尝试回车提交")
                ActionChains(driver).send_keys(Keys.ENTER).perform()

            time.sleep(5)
            driver.save_screenshot("debug_screenshots/3_final_result.png")

            page_source = driver.page_source.lower()
            if "success" in page_source or len(driver.find_elements(By.CLASS_NAME, "alert-success")) > 0:
                print("✅✅✅ 续期成功！")
                send_tg("✅ Katabump 续期成功！")
            else:
                print("❓ 未检测到成功标志，请检查截图")
                send_tg("⚠️ 脚本执行完毕，但未检测到明确成功信号，请检查 Artifacts 截图")
        
        else:
            print("ℹ️ 未找到 Renew 按钮 (可能无需续费或页面结构变更)")
            driver.save_screenshot("debug_screenshots/no_renew_button.png")

    except Exception as e:
        print(f"❌ 运行严重错误: {e}")
        send_tg(f"❌ 脚本运行出错: {e}")
        # 出错时截图
        try:
            driver.save_screenshot("debug_screenshots/error_state.png")
        except: pass
    
    finally:
        try:
            driver.quit()
        except: pass

if __name__ == "__main__":
    run()
