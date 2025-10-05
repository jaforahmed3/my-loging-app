from flask import Flask, render_template, request, jsonify, session, make_response
import requests
from bs4 import BeautifulSoup
from fpdf import FPDF
import base64
from io import BytesIO
import re

app = Flask(__name__)
app.secret_key = 'your_very_secret_and_random_key'  # একটি র‍্যান্ডম কী ব্যবহার করুন

# টার্গেট সরকারি ওয়েবসাইট
BASE_URL = "https://everify.bdris.gov.bd/"

# একটি সেশন অবজেক্ট তৈরি করা যা কুকি এবং হেডার সংরক্ষণ করবে
http_session = requests.Session()
http_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get-captcha')
def get_captcha():
    try:
        response = http_session.get(BASE_URL)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # নতুন id ব্যবহার করে ক্যাপচা ইমেজ ট্যাগ খুঁজে বের করা
        captcha_img_tag = soup.find('img', {'id': 'CaptchaImage'})
        if not captcha_img_tag:
            return jsonify({'success': False, 'error': 'Captcha image tag not found on the target website.'})
        
        captcha_url = BASE_URL.rstrip('/') + captcha_img_tag['src']
        
        # ক্যাপচা ইমেজটি বাইনারি হিসেবে ডাউনলোড করা
        captcha_image_response = http_session.get(captcha_url)
        if captcha_image_response.status_code != 200:
            return jsonify({'success': False, 'error': 'Failed to download captcha image.'})

        # ইমেজকে Base64-এ কনভার্ট করা
        captcha_base64 = "data:image/png;base64," + base64.b64encode(captcha_image_response.content).decode('utf-8')

        # ভেরিফিকেশন টোকেন এবং অন্যান্য প্রয়োজনীয় ইনপুট খুঁজে বের করা
        token = soup.find('input', {'name': '__RequestVerificationToken'})
        captcha_de_text = soup.find('input', {'name': 'CaptchaDeText'})

        if not token or not captcha_de_text:
            return jsonify({'success': False, 'error': 'Required form fields (token/captcha text) not found.'})

        # সেশনে কুকি এবং টোকেন সংরক্ষণ করা
        session['server_cookies'] = http_session.cookies.get_dict()
        session['token'] = token['value']
        session['captcha_de_text'] = captcha_de_text['value']

        return jsonify({'success': True, 'captcha': captcha_base64})
    except Exception as e:
        return jsonify({'success': False, 'error': f"An error occurred: {str(e)}"})

@app.route('/verify', methods=['POST'])
def verify_data():
    try:
        data = request.json
        brn = data.get('brn')
        dob = data.get('dob')
        captcha_text = data.get('captcha')
        
        # সেশন থেকে কুকি এবং টোকেন নেওয়া
        cookies = session.get('server_cookies')
        token = session.get('token')
        captcha_de_text = session.get('captcha_de_text')

        if not all([cookies, token, captcha_de_text]):
            return jsonify({'success': False, 'error': 'Session expired. Please refresh the page.'})

        # সরকারি সাইটের নতুন ফর্ম ফিল্ড অনুযায়ী ডেটা প্রস্তুত করা
        payload = {
            '__RequestVerificationToken': token,
            'UBRN': brn,
            'BirthDate': dob,
            'CaptchaDeText': captcha_de_text,
            'CaptchaInputText': captcha_text
        }

        # POST রিকোয়েস্ট পাঠানো
        # **গুরুত্বপূর্ণ:** ফর্মের action URL টিও যুক্ত করতে হবে
        form_action_url = BASE_URL + "UBRNVerification/Search"
        response = http_session.post(form_action_url, data=payload, cookies=cookies)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # ফলাফলের জন্য নতুন কনটেইনার বা এলিমেন্ট খুঁজে বের করা
        # **নোট:** ফলাফলের HTML গঠনও পরিবর্তিত হতে পারে। এটি এখন একটি সাধারণ প্যারাগ্রাফের মধ্যে থাকে।
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
            # যদি কোনো এরর মেসেজ থাকে, সেটা খুঁজে বের করা
            error_p = soup.find('p', class_='text-danger')
            if error_p and error_p.text.strip():
                return jsonify({'success': False, 'error': error_p.text.strip()})
            return jsonify({'success': False, 'error': 'Result not found. Please check the inputs or the website may have changed.'})

        return jsonify({'success': True, 'data': result_data})

    except Exception as e:
        return jsonify({'success': False, 'error': f"An unexpected error occurred during verification: {str(e)}"})


# PDF তৈরির জন্য Helper Class (এটি অপরিবর্তিত থাকবে)
class PDF(FPDF):
    def header(self):
        try:
            self.add_font('kalpurush', '', 'font/kalpurush.ttf', uni=True)
            self.set_font('kalpurush', '', 15)
        except RuntimeError:
            # ফন্ট লোড না হলে ফলব্যাক
            self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Jonmo Nibondhon Tothyo', 1, 1, 'C')

    def chapter_body(self, data):
        try:
            self.set_font('kalpurush', '', 12)
        except RuntimeError:
            self.set_font('Arial', '', 12)
        
        for key, value in data.items():
            # এনকোডিং সমস্যা এড়ানোর জন্য
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
