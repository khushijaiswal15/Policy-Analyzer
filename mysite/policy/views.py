from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Q
from urllib.parse import urlparse, urljoin, urldefrag
from .forms import UploadPDFForm, URLUploadForm
from .models import PolicyAnalysis, URLExtractionJob, PDFLink, ExtractedText
from .gemini import analyze_policy_pdf
import time
import requests
from bs4 import BeautifulSoup
import fitz  # PyMuPDF
from pdf2image import convert_from_bytes
import pytesseract
import cv2
import numpy as np
from PIL import Image
import tempfile
import os
from pdfminer.high_level import extract_text
from io import BytesIO

def extract_text_with_pdfminer(pdf_bytes):
    try:
        return extract_text(BytesIO(pdf_bytes)).strip()
    except Exception as e:
        print(f"[PDFMiner ERROR]: {e}")
        return None


# Tesseract path (adjust if needed)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def upload_pdf(request):
    if request.method == 'POST':
        form = UploadPDFForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.cleaned_data['pdf']
            result = analyze_policy_pdf(uploaded_file)
            PolicyAnalysis.objects.create(
                title=result['title'],
                date=result['date'],
                summary=result['summary'],
                affected=result['affected'],
                sector_impacts=result['sector_impacts'],
                most_sector=result['most_sector'],
                most_text=result['most_text'],
                pdf_file=uploaded_file,
                uploaded_from='file'
            )
            return render(request, 'result.html', {**result, 'form': form})
    else:
        form = UploadPDFForm()
    return render(request, 'result.html', {'form': form})


def upload_from_url(request):
    if request.method == 'POST':
        form = URLUploadForm(request.POST)
        if form.is_valid():
            url = form.cleaned_data['url']
            job = URLExtractionJob.objects.create(url=url)
            return redirect('monitor_extraction', job_id=job.id)
    else:
        form = URLUploadForm()
    return render(request, 'upload_from_url.html', {'form': form})


def is_valid_document_link(href):
    if not href:
        return False
    href, _ = urldefrag(href)
    if '?' in href or '#' in href:
        return False
    return (
        href.lower().endswith('.pdf') or
        href.lower().endswith('.html') or
        href.lower().endswith('.htm') or
        '/publications/' in href
    )


def extract_links_from_page(page_url, domain, job):
    count = 0
    try:
        response = requests.get(page_url, timeout=10)
        if response.status_code != 200:
            return 0
        soup = BeautifulSoup(response.text, 'html.parser')
        anchors = soup.find_all('a', href=True)

        for a in anchors:
            href = a['href']
            full_url = urljoin(page_url, href)
            full_url, _ = urldefrag(full_url)
            parsed = urlparse(full_url)

            if parsed.netloc != domain or parsed.scheme not in ['http', 'https']:
                continue

            if is_valid_document_link(full_url):
                link_type = 'pdf' if full_url.lower().endswith('.pdf') else 'html'
                if not PDFLink.objects.filter(link=full_url, job=job).exists():
                    PDFLink.objects.create(job=job, link=full_url, link_type=link_type)
                    count += 1
    except Exception as e:
        print(f"Error extracting page {page_url}: {e}")
    return count


def monitor_extraction(request, job_id):
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager

    job = get_object_or_404(URLExtractionJob, id=job_id)
    extracted_links = PDFLink.objects.filter(job=job)

    if job.status == 'in_progress':
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        visited_links = set()
        domain = urlparse(job.url).netloc

        try:
            driver.get(job.url)
            wait = WebDriverWait(driver, 10)
            page = 1
            while True:
                print(f"🔄 Crawling page {page}")
                time.sleep(2)

                anchors = driver.find_elements(By.XPATH, "//a[@href]")
                for a in anchors:
                    href = a.get_attribute("href")
                    if not href:
                        continue
                    full_url, _ = urldefrag(urljoin(driver.current_url, href))
                    parsed = urlparse(full_url)

                    if parsed.netloc != domain or parsed.scheme not in ['http', 'https']:
                        continue

                    if is_valid_document_link(full_url) and full_url not in visited_links:
                        visited_links.add(full_url)
                        link_type = 'pdf' if full_url.lower().endswith('.pdf') else 'html'
                        if not PDFLink.objects.filter(link=full_url, job=job).exists():
                            PDFLink.objects.create(job=job, link=full_url, link_type=link_type)

                try:
                    next_button = wait.until(
                        EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'next') or contains(text(),'Next')]"))
                    )
                    next_button.click()
                    page += 1
                except Exception:
                    print("❌ No more pages or next button not found.")
                    break
        finally:
            driver.quit()

        job.status = 'completed'
        job.save()
        extracted_links = PDFLink.objects.filter(job=job)

    pdf_count = extracted_links.filter(link_type='pdf').count()
    html_count = extracted_links.filter(link_type='html').count()
    total_count = extracted_links.count()

    return render(request, 'monitor.html', {
        'job': job,
        'extracted_links': extracted_links,
        'pdf_count': pdf_count,
        'html_count': html_count,
        'total_count': total_count,
    })


@require_POST
def pause_job(request, job_id):
    job = get_object_or_404(URLExtractionJob, id=job_id)
    job.status = 'paused'
    job.save()
    return redirect('monitor_extraction', job_id=job_id)


@require_POST
def resume_job(request, job_id):
    job = get_object_or_404(URLExtractionJob, id=job_id)
    job.status = 'in_progress'
    job.save()
    return redirect('monitor_extraction', job_id=job_id)


def view_saved(request):
    policies = PolicyAnalysis.objects.all().order_by('-date')
    return render(request, 'view_saved.html', {'policies': policies})


def view_uploaded_pdfs(request):
    policies = PolicyAnalysis.objects.filter(uploaded_from='file').order_by('-date')
    return render(request, 'view_uploaded_pdfs.html', {'policies': policies})


def view_url_pdfs(request):
    query = request.GET.get('q', '')
    links = PDFLink.objects.select_related('job').order_by('-uploaded_at')
    if query:
        links = links.filter(link__icontains=query)
    return render(request, 'view_url_pdfs.html', {'links': links, 'query': query})


def view_policy(request, policy_id):
    policy = get_object_or_404(PolicyAnalysis, id=policy_id)
    return render(request, 'detail.html', {'policy': policy})


def delete_policy(request, policy_id):
    policy = get_object_or_404(PolicyAnalysis, id=policy_id)
    policy.delete()
    messages.success(request, "Policy deleted successfully.")
    return redirect('view_saved')


@require_POST
def delete_pdf_link(request, link_id):
    link = get_object_or_404(PDFLink, id=link_id)
    link.delete()
    messages.success(request, "Link deleted successfully.")
    return redirect('view_url_pdfs')


def extract_text_directly_from_pdf(pdf_bytes):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        headings = []

        for page in doc:
            blocks = page.get_text("dict")["blocks"]
            for b in blocks:
                if "lines" in b:
                    for l in b["lines"]:
                        for s in l["spans"]:
                            if s["size"] > 12 and len(s["text"].strip()) > 3:
                                headings.append(s["text"].strip())
                            text += s["text"] + " "

        doc.close()
        if not text.strip():
          return None
        summary, highlighted = summarize_and_highlight(text)
        return f"HEADINGS:\n{', '.join(headings)}\n\nSUMMARY:\n{summary}\n\nFULL TEXT:\n{highlighted}"


    except Exception as e:
        print(f"[PyMuPDF ERROR]: {e}")
        return None



def extract_text_from_pdf_ocr(pdf_bytes):
    """Fallback OCR extraction for image-based PDFs."""
    try:
        images = convert_from_bytes(pdf_bytes, dpi=300)
        extracted_text = ""

        # Create temp directory to save images for debugging
        debug_dir = os.path.join(tempfile.gettempdir(), "pdf_debug_images")
        os.makedirs(debug_dir, exist_ok=True)

        for i, img in enumerate(images):
            img_path = os.path.join(debug_dir, f"page_{i+1}.png")
            img.save(img_path)

            # Preprocess image
            img_gray = np.array(img.convert("L"))
            blur = cv2.GaussianBlur(img_gray, (5, 5), 0)
            _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            pil_img = Image.fromarray(thresh)

            # OCR
            text = pytesseract.image_to_string(pil_img, lang='eng')
            extracted_text += f"\n\n--- Page {i + 1} ---\n{text.strip()}"

        return extracted_text.strip() or None
    except Exception as e:
        print(f"[OCR ERROR]: {e}")
        return None


from pdfminer.high_level import extract_text as extract_text_pdfminer

def extract_text_from_pdf_link(link):
    """Robust extraction from a PDF link using saved temp file + fallback logic."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(link.link, headers=headers, timeout=15)

        if 'application/pdf' not in response.headers.get('Content-Type', '').lower():
            print(f"[❌ Not a PDF] {link.link}")
            return None

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(response.content)
            tmp_path = tmp_file.name

        # 1. Try PyMuPDF (text + structure)
        try:
            doc = fitz.open(tmp_path)
            full_text = ""
            headings = []
            for page in doc:
                blocks = page.get_text("dict")["blocks"]
                for b in blocks:
                    if "lines" in b:
                        for l in b["lines"]:
                            for s in l["spans"]:
                                if s["size"] > 12 and len(s["text"].strip()) > 3:
                                    headings.append(s["text"].strip())
                                full_text += s["text"] + " "
            doc.close()
            if full_text.strip():
                summary, highlighted = summarize_and_highlight(full_text)
                os.remove(tmp_path)
                return f"HEADINGS:\n{', '.join(headings)}\n\nSUMMARY:\n{summary}\n\nFULL TEXT:\n{highlighted}"
        except Exception as e:
            print(f"[PyMuPDF ERROR] {link.link}: {e}")

        # 2. Try PDFMiner
        try:
            from pdfminer.high_level import extract_text as pdfminer_extract
            text = pdfminer_extract(tmp_path)
            if text and text.strip():
                summary, highlighted = summarize_and_highlight(text)
                os.remove(tmp_path)
                return f"SUMMARY:\n{summary}\n\nFULL TEXT:\n{highlighted}"
        except Exception as e:
            print(f"[PDFMiner ERROR] {link.link}: {e}")

        # 3. Fallback to OCR
        try:
            images = convert_from_bytes(open(tmp_path, "rb").read(), dpi=300)
            extracted_text = ""
            for i, img in enumerate(images):
                img_gray = np.array(img.convert("L"))
                blur = cv2.GaussianBlur(img_gray, (5, 5), 0)
                _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                pil_img = Image.fromarray(thresh)
                text = pytesseract.image_to_string(pil_img, lang='eng')
                extracted_text += f"\n\n--- Page {i + 1} ---\n{text.strip()}"

            os.remove(tmp_path)
            if extracted_text.strip():
                summary, highlighted = summarize_and_highlight(extracted_text)
                return f"SUMMARY:\n{summary}\n\nFULL TEXT:\n{highlighted}"
        except Exception as e:
            print(f"[OCR ERROR] {link.link}: {e}")

        os.remove(tmp_path)
        return None

    except Exception as e:
        print(f"[❌ ERROR] extract_text_from_pdf_link({link.link}): {e}")
        return None



def extract_text_from_html_url(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Remove hidden tags
        for tag in soup(['script', 'style', 'meta', 'noscript', 'iframe']):
            tag.decompose()

        result = []

        for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'ul', 'ol', 'li']):
            if tag.name.startswith('h'):
                result.append(f"\n# {tag.get_text(strip=True)}")
            elif tag.name in ['ul', 'ol']:
                continue  # Lists handled in <li>
            elif tag.name == 'li':
                result.append(f"• {tag.get_text(strip=True)}")
            else:
                result.append(tag.get_text(strip=True))

        full_text = "\n".join(result)
        summary, highlighted = summarize_and_highlight(full_text)

        return f"SUMMARY:\n{summary}\n\nFULL TEXT:\n{highlighted}"

    except Exception as e:
        print(f"[HTML ERROR] {url}: {e}")
        return None



@require_POST
def extract_next_100_links(request):
    unprocessed_links = PDFLink.objects.filter(
        ~Q(id__in=ExtractedText.objects.values_list('link_id', flat=True))
    )[:100]

    success_count = 0
    skipped_count = 0

    for link in unprocessed_links:
        text = None
        if link.link_type == 'pdf':
            text = extract_text_from_pdf_link(link.link)
        elif link.link_type == 'html':
            text = extract_text_from_html_url(link.link)

        if text:
            _, created = ExtractedText.objects.get_or_create(
                link=link,
                defaults={'text': text[:10000]}
            )
            if created:
                success_count += 1
            else:
                skipped_count += 1

    messages.success(
        request,
        f"✅ Processed {len(unprocessed_links)} links. Extracted from {success_count}, skipped {skipped_count}."
    )
    return redirect('view_url_pdfs')


def view_extracted_texts(request):
    texts = ExtractedText.objects.all().order_by('-extracted_at')
    total_count = texts.count()
    return render(request, 'view_extracted_texts.html', {
        'texts': texts,
        'total_count': total_count,
    })



def view_text_detail(request, pk):
    extracted = get_object_or_404(ExtractedText, pk=pk)
    return render(request, 'view_extracted_text.html', {'item': extracted})


def delete_extracted_text(request, pk):
    text = get_object_or_404(ExtractedText, pk=pk)
    text.delete()
    messages.success(request, "Extracted text deleted successfully.")
    return redirect('view_extracted_texts')
def summarize_and_highlight(text, keywords=None):
    import re
    sentences = re.split(r'(?<=[.!?]) +', text)
    summary = ' '.join(sentences[:5])

    if not keywords:
        keywords = ['policy', 'impact', 'regulation', 'sector', 'compliance']

    for kw in keywords:
        text = re.sub(rf'\b({re.escape(kw)})\b', r'**\1.upper()**', text, flags=re.IGNORECASE)
        summary = re.sub(rf'\b({re.escape(kw)})\b', r'**\1.upper()**', summary, flags=re.IGNORECASE)

    return summary.strip(), text.strip()
