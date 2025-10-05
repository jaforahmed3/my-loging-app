document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('verify-form');
    const captchaImage = document.getElementById('captcha-image');
    const loader = document.getElementById('loader');
    const resultContainer = document.getElementById('result-container');
    const resultData = document.getElementById('result-data');
    const errorContainer = document.getElementById('error-container');
    const errorMessage = document.getElementById('error-message');
    const downloadPdfBtn = document.getElementById('download-pdf-btn');

    let verifiedData = null;

    // পেজ লোড হওয়ার সাথে সাথে ক্যাপচা লোড করার ফাংশন
    async function loadCaptcha() {
        try {
            const response = await fetch('/get-captcha');
            const data = await response.json();
            if (data.success) {
                captchaImage.src = data.captcha;
            } else {
                showError('ক্যাপচা লোড করা সম্ভব হয়নি।');
            }
        } catch (error) {
            showError('সার্ভারের সাথে সংযোগে সমস্যা হয়েছে।');
        }
    }

    // ফরম সাবমিট হলে ডেটা যাচাই করার ফাংশন
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        hideAllSections();
        loader.style.display = 'block';

        const brn = document.getElementById('brn').value;
        const dobInput = document.getElementById('dob').value;
        const captcha = document.getElementById('captcha').value;
        
        // Date format YYYY-MM-DD
        const dob = dobInput;

        try {
            const response = await fetch('/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ brn, dob, captcha })
            });

            const result = await response.json();
            loader.style.display = 'none';

            if (result.success) {
                displayResult(result.data);
                verifiedData = result.data; // PDF এর জন্য ডেটা সংরক্ষণ
            } else {
                showError(result.error);
                loadCaptcha(); // ভুল হলে নতুন ক্যাপচা লোড
            }

        } catch (error) {
            loader.style.display = 'none';
            showError('একটি অপ্রত্যাশিত সমস্যা হয়েছে।');
            loadCaptcha();
        }
    });
    
    // PDF ডাউনলোড বাটন ক্লিক হলে
    downloadPdfBtn.addEventListener('click', async () => {
        if (!verifiedData) {
            showError('ডাউনলোড করার জন্য কোনো তথ্য নেই।');
            return;
        }

        try {
            const response = await fetch('/download-pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ data: verifiedData })
            });
            
            if(response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = 'birth_certificate_info.pdf';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
            } else {
                showError('PDF ডাউনলোড করা সম্ভব হয়নি।');
            }

        } catch (error) {
            showError('PDF ডাউনলোডে সমস্যা হয়েছে।');
        }
    });

    function displayResult(data) {
        resultData.innerHTML = '';
        const table = document.createElement('table');
        for (const key in data) {
            const row = table.insertRow();
            const cell1 = row.insertCell();
            cell1.textContent = key;
            const cell2 = row.insertCell();
            cell2.textContent = data[key];
        }
        resultData.appendChild(table);
        resultContainer.style.display = 'block';
    }

    function showError(message) {
        errorMessage.textContent = message;
        errorContainer.style.display = 'block';
    }

    function hideAllSections() {
        loader.style.display = 'none';
        resultContainer.style.display = 'none';
        errorContainer.style.display = 'none';
    }

    // Initial captcha load
    loadCaptcha();
});
