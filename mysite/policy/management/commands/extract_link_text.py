# policy/management/commands/extract_link_text_batch.py

from django.core.management.base import BaseCommand
from policy.models import PDFLink, ExtractedText
import requests
import tempfile
import os
from pdfminer.high_level import extract_text as extract_text_pdfminer
from pdf2image import convert_from_path
import pytesseract
from django.conf import settings

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"  # ✅ UPDATE THIS if different on your PC

def extract_text_with_ocr(pdf_path):
    try:
        images = convert_from_path(pdf_path, dpi=300)
        text = ""
        for img in images:
            text += pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        return ""

class Command(BaseCommand):
    help = 'Extracts text from saved PDF links (batch of 100) and saves to ExtractedText model.'

    def handle(self, *args, **options):
        links = PDFLink.objects.filter(processed=False)[:100]
        if not links:
            self.stdout.write(self.style.WARNING("✅ No unprocessed links found."))
            return

        for link in links:
            try:
                response = requests.get(link.url)
                if response.status_code == 200:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
                        temp_pdf.write(response.content)
                        temp_pdf_path = temp_pdf.name

                    # Try pdfminer first
                    extracted_text = extract_text_pdfminer(temp_pdf_path).strip()

                    # If text is empty, use OCR
                    if not extracted_text:
                        extracted_text = extract_text_with_ocr(temp_pdf_path)

                    if extracted_text:
                        ExtractedText.objects.create(link=link, extracted_text=extracted_text)
                        self.stdout.write(self.style.SUCCESS(f"✅ Extracted text from: {link.url}"))
                    else:
                        self.stdout.write(self.style.WARNING(f"⚠️ No text found in: {link.url}"))

                    # Mark as processed
                    link.processed = True
                    link.save()

                    os.remove(temp_pdf_path)
                else:
                    self.stdout.write(self.style.ERROR(f"❌ Failed to download: {link.url}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Error with link {link.url}: {e}"))

        self.stdout.write(self.style.SUCCESS("✅ Finished extracting text for current batch."))
