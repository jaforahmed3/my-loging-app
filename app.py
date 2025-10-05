
from flask import Flask, render_template, request, jsonify, session, make_response
import requests
from bs4 import BeautifulSoup
from fpdf import FPDF
import base64
from io import BytesIO
import warnings

# SSL Warning উপেক্ষা করার জন্য
from requests.packages.urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

app = Flask(__name__)
app.secret_key = 'a_truly_final_and_very_random_secret_key'

BASE_URL = "https://everify.bdris.gov.bd/"

http_session = requests.Session()
http_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get-captcha')
def get_captcha():
    try:
        response = http_session.get(BASE_URL, timeout=30, verify=False)
        
        if response.status_code != 200:
            return jsonify({'success': False, 'error': f'Server Connection Failed. Status: {response.status_code}'})
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        captcha_img_tag = soup.find('img', {'id': 'CaptchaImage'})
        if not captcha_img_tag or not captcha_img_tag.get('src'):
            return jsonify({'success': False, 'error': 'Captcha Image Source Not Found.'})
        
        captcha_url = BASE_URL.rstrip('/') + captcha_img_tag['src']
        
        captcha_image_response = http_session.get(captcha_url, timeout=30, verify=False)
        
        if captcha_image_response.status_code != 200:
            return jsonify({'success': False, 'error': 'Failed to Download Captcha Image.'})
            
        # ছবির ধরন (Content-Type) নিজে থেকে শনাক্ত করা
        content_type = captcha_image_response.headers.get('content-type', 'image/png')
        
        # Base64 ডেটা সঠিকভাবে তৈরি করা
        encoded_image = base64.b64encode(captcha_image_response.content).decode('utf-8')
        captcha_base64 = f"data:{content_type};base64,{encoded_image}"

        token = soup.find('input', {'name': '__RequestVerificationToken'})
        captcha_de_text = soup.find('input', {'name': 'CaptchaDeText'})
        
        if not token or not captcha_de_text:
            return jsonify({'success': False, 'error': 'Required Form Fields Not Found.'})
        
        session['server_cookies'] = http_session.cookies.get_dict()
        session['token'] = token['value']
        session['captcha_de_text'] = captcha_de_text['value']

        return jsonify({'success': True, 'captcha': captcha_base64})

    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'Connection to government server timed out.'})
    except Exception as e:
        return jsonify({'success': False, 'error': f"A critical error occurred: {e}"})

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
        response = http_session.post(form_action_url, data=payload, cookies=cookies, verify=False, timeout=30)
        
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
                if key and value: # নিশ্চিত করা যে কী এবং ভ্যালু খালি নয়
                    result_data[key] = value
                    found = True

        if not found:
            error_p = soup.find('p', class_='text-danger')
            if error_p and error_p.text.strip():
                return jsonify({'success': False, 'error': error_p.text.strip()})
            return jsonify({'success': False, 'error': 'Result not found. Check inputs or website may have changed.'})

        return jsonify({'success': True, 'data': result_data})

    except Exception as e:
        return jsonify({'success': False, 'error': f"An unexpected error occurred during verification: {e}"})

class PDF(FPDF):
    def header(self):
        try:
            self.add_font('kalpurush', '', 'font/kalpurush.ttf', uni=True)
            self.set_font('kalpurush', '', 15)
            self.cell(0, 10, 'জন্ম নিবন্ধন তথ্য', 1, 1, 'C')
        except RuntimeError:
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, 'Jonmo Nibondhon Tothyo', 1, 1, 'C')

    def chapter_body(self, data):
        try:
            self.set_font('kalpurush', '', 12)
        except RuntimeError:
            self.set_font('Arial', '', 12)
        
        for key, value in data.items():
            try:
                self.cell(80, 10, f'{key}:', 1, 0, 'L')
                self.cell(110, 10, value, 1, 1, 'L')
            except UnicodeEncodeError:
                safe_key = key.encode('latin-1', 'replace').decode('latin-1')
                safe_value = value.encode('latin-1', 'replace').decode('latin-1')
                self.cell(80, 10, f'{safe_key}:', 1, 0, 'L')
                self.cell(110, 10, safe_value, 1, 1, 'L')

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
    app.run(host='0.0.0.0', port=5000)
