from flask import Flask, render_template, request, jsonify, session, make_response
import requests
from bs4 import BeautifulSoup
from fpdf import FPDF
import base64
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'your_very_secret_and_random_key_for_debugging'

BASE_URL = "https://everify.bdris.gov.bd/"

http_session = requests.Session()
http_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get-captcha')
def get_captcha():
    print("-----------------------------------------")
    print("'/get-captcha' অনুরোধ শুরু হয়েছে...")
    try:
        print("সরকারি সাইটে সংযোগ করার চেষ্টা চলছে...")
        response = http_session.get(BASE_URL, timeout=20, verify=False) # ২০ সেকেন্ড টাইমআউট যোগ করা হলো
        print(f"সরকারি সাইটে সংযোগের স্ট্যাটাস কোড: {response.status_code}")

        if response.status_code != 200:
            print("সংযোগ ব্যর্থ হয়েছে। ওয়েবসাইটটি হয়তো ডাউন অথবা আমাদের ব্লক করেছে।")
            return jsonify({'success': False, 'error': f'Failed to connect to the government server. Status: {response.status_code}'})
        
        print("সংযোগ সফল। HTML পার্স করা হচ্ছে...")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # নতুন id ব্যবহার করে ক্যাপচা ইমেজ ট্যাগ খুঁজে বের করা
        captcha_img_tag = soup.find('img', {'id': 'CaptchaImage'})
        print(f"ক্যাপচা ইমেজ ট্যাগ পাওয়া গেছে কিনা? {'হ্যাঁ' if captcha_img_tag else 'না'}")

        if not captcha_img_tag:
            print("HTML কোডের ভেতরে 'CaptchaImage' id খুঁজে পাওয়া যায়নি। ওয়েবসাইট পরিবর্তন হয়েছে।")
            # ডিবাগিং এর জন্য HTML প্রিন্ট করা হচ্ছে
            # print("--- পাওয়া HTML এর শুরু ---")
            # print(response.text[:1000]) # প্রথম ১০০০ অক্ষর প্রিন্ট করা হলো
            # print("--- পাওয়া HTML এর শেষ ---")
            return jsonify({'success': False, 'error': 'Captcha image tag not found. The website structure may have changed.'})
        
        print("ক্যাপচা ইমেজ ট্যাগ সফলভাবে পাওয়া গেছে।")
        captcha_url = BASE_URL.rstrip('/') + captcha_img_tag['src']
        print(f"ক্যাপচা ছবির URL: {captcha_url}")

        captcha_image_response = http_session.get(captcha_url)
        captcha_base64 = "data:image/png;base64," + base64.b64encode(captcha_image_response.content).decode('utf-8')

        token = soup.find('input', {'name': '__RequestVerificationToken'})
        captcha_de_text = soup.find('input', {'name': 'CaptchaDeText'})
        print(f"টোকেন পাওয়া গেছে কিনা? {'হ্যাঁ' if token else 'না'}")

        if not token or not captcha_de_text:
            print("টোকেন বা ক্যাপচা টেক্সট ফিল্ড পাওয়া যায়নি।")
            return jsonify({'success': False, 'error': 'Required form fields (token/captcha text) not found.'})
        
        session['server_cookies'] = http_session.cookies.get_dict()
        session['token'] = token['value']
        session['captcha_de_text'] = captcha_de_text['value']

        print("সফলভাবে ক্যাপচা এবং টোকেন পাওয়া গেছে। ওয়েবসাইটে পাঠানো হচ্ছে।")
        print("-----------------------------------------")
        return jsonify({'success': True, 'captcha': captcha_base64})

    except requests.exceptions.RequestException as e:
        print(f"একটি মারাত্মক নেটওয়ার্ক এরর হয়েছে: {e}")
        print("-----------------------------------------")
        return jsonify({'success': False, 'error': f"A critical network error occurred: {e}"})
    except Exception as e:
        print(f"একটি অপ্রত্যাশিত মারাত্মক এরর হয়েছে: {e}")
        print("-----------------------------------------")
        return jsonify({'success': False, 'error': f"An unexpected critical error occurred: {e}"})

# ----- বাকি কোড অপরিবর্তিত থাকবে -----
# ... (verify_data এবং PDF ডাউনলোড করার ফাংশনগুলো যেমন ছিল তেমনই থাকবে)
@app.route('/verify', methods=['POST'])
def verify_data():
    try:
        data = request.json
        brn = data.get('brn')
        dob = data.get('dob')
        captcha_text = data.get('captcha')
        
        cookies = session.get('server_cookies')
        token = session.get('token')
        captcha_de_text = session.get('captcha_de_text')

        if not all([cookies, token, captcha_de_text]):
            return jsonify({'success': False, 'error': 'Session expired. Please refresh the page.'})

        payload = {
            '__RequestVerificationToken': token,
            'UBRN': brn,
            'BirthDate': dob,
            'CaptchaDeText': captcha_de_text,
            'CaptchaInputText': captcha_text
        }
        
        form_action_url = BASE_URL + "UBRNVerification/Search"
        response = http_session.post(form_action_url, data=payload, cookies=cookies, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        result_paragraphs = soup.find_all('p')
        
        result_data = {}
        found = False
        for p in result_paragraphs:
            text = p.get_text(strip=True)
            if ":" in text:
                parts = text.split(':', 1)
                key = parts[0].strip()
                value = parts[1].strip()
                result_data[key] = value
                found = True

        if not found:
            error_p = soup.find('p', class_='text-danger')
            if error_p and error_p.text.strip():
                return jsonify({'success': False, 'error': error_p.text.strip()})
            return jsonify({'success': False, 'error': 'Result not found. Please check the inputs or the website may have changed.'})

        return jsonify({'success': True, 'data': result_data})

    except Exception as e:
        return jsonify({'success': False, 'error': f"An unexpected error occurred during verification: {str(e)}"})

class PDF(FPDF):
    def header(self):
        try:
            self.add_font('kalpurush', '', 'font/kalpurush.ttf', uni=True)
            self.set_font('kalpurush', '', 15)
        except RuntimeError:
            self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Jonmo Nibondhon Tothyo', 1, 1, 'C')

    def chapter_body(self, data):
        try:
            self.set_font('kalpurush', '', 12)
        except RuntimeError:
            self.set_font('Arial', '', 12)
        
        for key, value in data.items():
            safe_key = key.encode('latin-1', 'replace').decode('latin-1')
            safe_value = value.encode('latin-1', 'replace').decode('latin-1')
            self.cell(80, 10, f'{safe_key}:', 1, 0)
            self.cell(110, 10, safe_value, 1, 1)

@app.route('/download-pdf', methods=['POST'])
def download_pdf():
    data = request.json.get('data')
    if not data:
        return "No data provided", 400
    
    pdf = PDF()
    pdf.add_page()
    pdf.chapter_body(data)
    
    pdf_output = pdf.output(dest='S').encode('latin-1')
    
    response = make_response(pdf_output)
    response.headers.set('Content-Type', 'application/pdf')
    response.headers.set('Content-Disposition', 'attachment', filename='birth_certificate_info.pdf')
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
