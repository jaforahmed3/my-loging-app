from flask import Flask, render_template, request, jsonify, session
import base64
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

app = Flask(__name__)
app.secret_key = 'a_very_powerful_and_final_secret_key'

# সেলেনিয়াম WebDriver সেটআপ করার ফাংশন
def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # ব্রাউজার না দেখিয়ে কাজ করবে
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    # Render.com এ Chrome এর জন্য নির্দিষ্ট পথ
    try:
        service = ChromeService(executable_path="/usr/bin/google-chrome-stable")
    except:
        service = ChromeService(ChromeDriverManager().install())
        
    driver = webdriver.Chrome(service=service, options=options)
    return driver

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get-captcha')
def get_captcha():
    driver = None
    try:
        driver = setup_driver()
        driver.get("https://everify.bdris.gov.bd/")
        
        # ক্যাপচা ছবিটি লোড হওয়ার জন্য ১০ সেকেন্ড অপেক্ষা করা
        wait = WebDriverWait(driver, 10)
        captcha_element = wait.until(EC.presence_of_element_located((By.ID, "CaptchaImage")))
        
        # ক্যাপচা ছবির স্ক্রিনশট নেওয়া
        captcha_screenshot_base64 = captcha_element.screenshot_as_base64
        captcha_data_url = f"data:image/png;base64,{captcha_screenshot_base64}"
        
        # কুকি এবং টোকেন সংগ্রহ করা
        cookies = driver.get_cookies()
        token = driver.find_element(By.NAME, "__RequestVerificationToken").get_attribute("value")
        captcha_de_text = driver.find_element(By.NAME, "CaptchaDeText").get_attribute("value")

        session['cookies'] = {cookie['name']: cookie['value'] for cookie in cookies}
        session['token'] = token
        session['captcha_de_text'] = captcha_de_text

        return jsonify({'success': True, 'captcha': captcha_data_url})

    except Exception as e:
        return jsonify({'success': False, 'error': f"An error occurred: {str(e)}"})
    finally:
        if driver:
            driver.quit()

@app.route('/verify', methods=['POST'])
def verify_data():
    # এই অংশটি এখন আর কাজ করবে না কারণ সেলেনিয়াম ছাড়া POST রিকোয়েস্ট পাঠানো কঠিন হবে।
    # এটি ভবিষ্যতের জন্য একটি জটিল কাজ। আপাতত আমরা শুধু ক্যাপচা লোড করার দিকে মনোযোগ দিচ্ছি।
    return jsonify({'success': False, 'error': 'Verification part is under development with new method.'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
