from mistralai import Mistral
import os
import base64
from dotenv import load_dotenv
from pypdf import PdfReader, PdfWriter
from io import BytesIO

# Load environment variables from .env file
load_dotenv()

# PDF file path
pdf_path = "pdf/Perangkaan-Agromakanan-Malaysia-2024.pdf"

# Extract page 3 from PDF
print("Extracting page 17 from PDF...")
try:
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    
    if total_pages < 17:
        print(f"Error: PDF only has {total_pages} page(s). Page 17 does not exist.")
        exit(1)
    
    # Create a new PDF with only page 17 (0-indexed, so page 17 is index 16)
    writer = PdfWriter()
    writer.add_page(reader.pages[16])  # Page 17 is at index 16
    
    # Write to bytes buffer
    buffer = BytesIO()
    writer.write(buffer)
    buffer.seek(0)
    
    # Convert PDF page to base64
    pdf_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
except Exception as e:
    print(f"Error extracting page from PDF: {e}")
    exit(1)

# Process with Mistral OCR
print("Processing page 17 with OCR...")
api_key = os.getenv("MISTRAL_API_KEY", "")
if not api_key:
    print("Error: MISTRAL_API_KEY environment variable is not set")
    exit(1)

try:
    client = Mistral(api_key=api_key)
    
    ocr_response = client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{pdf_base64}",
        },
    )
    
    print("\n=== OCR Output for Page 17 ===")
    print(ocr_response)
    
except Exception as e:
    print(f"Error processing OCR: {e}")
    print("\nNote: If you see an API format error, the document format might need adjustment.")
    print("Check Mistral OCR API documentation for the correct format.")
    raise