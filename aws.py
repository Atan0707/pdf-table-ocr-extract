import boto3
import os
from dotenv import load_dotenv
from pypdf import PdfReader, PdfWriter
from io import BytesIO

# Load environment variables from .env file
load_dotenv()

# PDF file path
pdf_path = "pdf/Perangkaan-Agromakanan-Malaysia-2024.pdf"

# Extract page 17 from PDF
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
    
    # Get PDF bytes for Textract
    pdf_bytes = buffer.getvalue()
    
except Exception as e:
    print(f"Error extracting page from PDF: {e}")
    exit(1)

# Process with AWS Textract
print("Processing page 17 with AWS Textract...")

# Get AWS credentials from environment variables
aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
aws_region = os.getenv("AWS_REGION", "us-east-1")  # Default to us-east-1

if not aws_access_key_id or not aws_secret_access_key:
    print("Error: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables must be set")
    exit(1)

try:
    # Initialize Textract client
    textract_client = boto3.client(
        'textract',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=aws_region
    )
    
    # Call Textract detect_document_text API
    # This works for single-page PDFs/images
    response = textract_client.detect_document_text(
        Document={
            'Bytes': pdf_bytes
        }
    )
    
    print("\n=== OCR Output for Page 17 ===")
    
    # Extract and print text blocks
    extracted_text = []
    for block in response.get('Blocks', []):
        if block['BlockType'] == 'LINE':
            extracted_text.append(block['Text'])
    
    # Print full response for comparison
    print("\n--- Full Textract Response ---")
    print(response)
    
    # Print extracted text in readable format
    print("\n--- Extracted Text (Lines) ---")
    print('\n'.join(extracted_text))
    
except Exception as e:
    print(f"Error processing OCR: {e}")
    print("\nNote: Make sure AWS credentials are correctly configured.")
    print("Check AWS Textract API documentation for the correct format.")
    raise

