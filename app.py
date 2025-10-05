from flask import Flask, render_template, request, jsonify, session, make_response
import requests
from bs4 import BeautifulSoup
from fpdf import FPDF
import base64
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'your_very_secret_key'  # একটি র‍্যান্ডম কী ব্যবহার করুন

# টার্গেট সরকারি ওয়েবসাইট
BASE_URL = "https://everify.bdris.gov.bd/"

# একটি সেশন অবজেক্ট তৈরি করা যা কুকি সংরক্ষণ করবে
http_session = requests.Session()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get-captcha')
def get_captcha():
    try:
        # সরকারি সাইটের হোমপেজে গিয়ে সেশন শুরু করা
        response = http_session.get(BASE_URL)
        soup = BeautifulSoup(response.text, 'html.parser')

        # ক্যাপচা ইমেজ ট্যাগ খুঁজে বের করা
        # **গুরুত্বপূর্ণ:** সরকারি সাইট পরিবর্তন হলে এই 'id' পরিবর্তন হতে পারে
        captcha_img_tag = soup.find('img', {'id': 'captcha_image'})
        if not captcha_img_tag:
            return jsonify({'success': False, 'error': 'Captcha image not found on the target website.'})

        captcha_base64 = captcha_img_tag['src']
        
        # সেশন কুকি সংরক্ষণ করা
        session['server_cookies'] = http_session.cookies.get_dict()

        return jsonify({'success': True, 'captcha': captcha_base64})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/verify', methods=['POST'])
def verify_data():
    try:
        data = request.json
        brn = data.get('brn')
        dob = data.get('dob')
        captcha_text = data.get('captcha')
        
        # সেশনে থাকা কুকি ব্যবহার করা
        cookies = session.get('server_cookies')
        if not cookies:
            return jsonify({'success': False, 'error': 'Session expired. Please refresh the page.'})

        # ফরম সাবমিট করার জন্য ডেটা প্রস্তুত করা
        # **গুরুত্বপূর্ণ:** এই 'name' গুলো সরকারি সাইটের ফর্ম ফিল্ড অনুযায়ী হতে হবে
        payload = {
            'brn': brn,
            'dob': dob,
            'captcha': captcha_text,
        }

        # POST রিকোয়েস্ট পাঠানো
        response = http_session.post(BASE_URL, data=payload, cookies=cookies)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # ফলাফল টেবিল খুঁজে বের করা
        result_divs = soup.find_all('div', class_='col-md-6')
        
        if not result_divs or len(result_divs) < 2:
            # যদি কোনো এরর মেসেজ থাকে, সেটা খুঁজে বের করা
            error_div = soup.find('div', class_='alert-danger')
            if error_div:
                return jsonify({'success': False, 'error': error_div.text.strip()})
            return jsonify({'success': False, 'error': 'Could not find the result. Please check the inputs.'})

        result_data = {}
        for div in result_divs:
            labels = div.find_all('label')
            if len(labels) == 2:
                key = labels[0].text.strip().replace(':', '')
                value = labels[1].text.strip()
                result_data[key] = value
        
        if not result_data:
            return jsonify({'success': False, 'error': 'No data found. The information may be incorrect.'})
            
        return jsonify({'success': True, 'data': result_data})

    except Exception as e:
        return jsonify({'success': False, 'error': f"An unexpected error occurred: {str(e)}"})

# PDF তৈরির জন্য Helper Class
class PDF(FPDF):
    def header(self):
        self.add_font('kalpurush', '', 'font/kalpurush.ttf', uni=True)
        self.set_font('kalpurush', '', 15)
        self.cell(0, 10, 'জন্ম নিবন্ধন তথ্য', 1, 1, 'C')

    def chapter_body(self, data):
        self.set_font('kalpurush', '', 12)
        for key, value in data.items():
            self.cell(80, 10, f'{key}:', 1, 0)
            self.cell(110, 10, value, 1, 1)

@app.route('/download-pdf', methods=['POST'])
def download_pdf():
    data = request.json.get('data')
    if not data:
        return "No data provided", 400
    
    pdf = PDF()
    pdf.add_page()
    pdf.chapter_body(data)
    
    pdf_output = pdf.output(dest='S').encode('latin1')
    
    response = make_response(pdf_output)
    response.headers.set('Content-Type', 'application/pdf')
    response.headers.set('Content-Disposition', 'attachment', filename='birth_certificate_info.pdf')
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
