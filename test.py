from mistralai import Mistral
import os
import base64
import csv
import json
import re
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
    
    # Convert OCR response to CSV
    print("\n=== Converting OCR output to CSV ===")
    csv_filename = "ocr_output_page_17.csv"
    
    def parse_markdown_table(markdown_text):
        """Parse markdown table and return list of rows, handling multi-line cells"""
        lines = markdown_text.split('\n')
        rows = []
        current_row_parts = []
        
        for line in lines:
            line_stripped = line.strip()
            
            # Check if this line starts with |
            if line_stripped.startswith('|'):
                # Check if this is a separator line (e.g., | --- | --- |)
                if line_stripped.endswith('|') and all(c in '| -:' for c in line_stripped.replace(' ', '')):
                    # Skip separator lines, but finish current row if any
                    if current_row_parts:
                        # Join and parse the row
                        row_text = ' '.join(current_row_parts).strip()
                        if row_text.startswith('|') and row_text.endswith('|'):
                            cells = [cell.strip() for cell in row_text[1:-1].split('|')]
                            if cells and not cells[0]:
                                cells = cells[1:]
                            if cells and not cells[-1]:
                                cells = cells[:-1]
                            if cells:
                                rows.append(cells)
                        current_row_parts = []
                    continue
                
                # If we have accumulated row parts and this line starts with |, finish previous row
                if current_row_parts and line_stripped.startswith('|'):
                    row_text = ' '.join(current_row_parts).strip()
                    if row_text.startswith('|') and row_text.endswith('|'):
                        cells = [cell.strip() for cell in row_text[1:-1].split('|')]
                        if cells and not cells[0]:
                            cells = cells[1:]
                        if cells and not cells[-1]:
                            cells = cells[:-1]
                        if cells:
                            rows.append(cells)
                    current_row_parts = []
                
                # Add this line to current row
                current_row_parts.append(line_stripped)
                
                # If this line ends with |, we have a complete row
                if line_stripped.endswith('|'):
                    row_text = ' '.join(current_row_parts).strip()
                    cells = [cell.strip() for cell in row_text[1:-1].split('|')]
                    if cells and not cells[0]:
                        cells = cells[1:]
                    if cells and not cells[-1]:
                        cells = cells[:-1]
                    if cells:
                        rows.append(cells)
                    current_row_parts = []
            elif current_row_parts:
                # This is a continuation line (part of a multi-line cell)
                current_row_parts.append(line_stripped)
        
        # Handle any remaining row
        if current_row_parts:
            row_text = ' '.join(current_row_parts).strip()
            if row_text.startswith('|') and row_text.endswith('|'):
                cells = [cell.strip() for cell in row_text[1:-1].split('|')]
                if cells and not cells[0]:
                    cells = cells[1:]
                if cells and not cells[-1]:
                    cells = cells[:-1]
                if cells:
                    rows.append(cells)
        
        return rows
    
    try:
        # Extract markdown from OCR response pages
        markdown_tables = []
        
        # Debug: Print response type and attributes
        print(f"\n=== Debug: OCR Response Type ===")
        print(f"Type: {type(ocr_response)}")
        print(f"Has 'pages' attr: {hasattr(ocr_response, 'pages')}")
        
        # Check if ocr_response has pages attribute
        if hasattr(ocr_response, 'pages'):
            print(f"Found 'pages' attribute, type: {type(ocr_response.pages)}")
            print(f"Number of pages: {len(ocr_response.pages) if ocr_response.pages else 0}")
            for idx, page in enumerate(ocr_response.pages):
                print(f"Page {idx} type: {type(page)}")
                print(f"Page {idx} has 'markdown' attr: {hasattr(page, 'markdown')}")
                if hasattr(page, 'markdown'):
                    markdown_content = page.markdown
                    print(f"Page {idx} markdown length: {len(markdown_content) if markdown_content else 0}")
                    if markdown_content:
                        markdown_tables.append(markdown_content)
                        print(f"Added markdown from page {idx}")
        elif hasattr(ocr_response, '__dict__'):
            ocr_dict = ocr_response.__dict__
            print(f"Using __dict__, keys: {list(ocr_dict.keys())}")
            if 'pages' in ocr_dict:
                for idx, page in enumerate(ocr_dict['pages']):
                    if hasattr(page, 'markdown') and page.markdown:
                        markdown_tables.append(page.markdown)
                    elif isinstance(page, dict) and 'markdown' in page:
                        markdown_tables.append(page['markdown'])
        elif isinstance(ocr_response, dict):
            print(f"OCR response is a dict, keys: {list(ocr_response.keys())}")
            if 'pages' in ocr_response:
                for page in ocr_response['pages']:
                    if isinstance(page, dict) and 'markdown' in page:
                        markdown_tables.append(page['markdown'])
                    elif hasattr(page, 'markdown'):
                        markdown_tables.append(page.markdown)
        
        print(f"\n=== Debug: Extracted {len(markdown_tables)} markdown table(s) ===")
        
        # Write CSV file
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            if markdown_tables:
                # Process each markdown table
                for table_idx, markdown_content in enumerate(markdown_tables):
                    print(f"\nProcessing markdown table {table_idx + 1}...")
                    print(f"Markdown preview (first 200 chars): {markdown_content[:200]}")
                    
                    # Extract table from markdown
                    rows = parse_markdown_table(markdown_content)
                    print(f"Parsed {len(rows)} rows from markdown")
                    
                    if rows:
                        # Write rows to CSV
                        for row in rows:
                            writer.writerow(row)
                        
                        # Add empty row between tables if multiple tables
                        if table_idx < len(markdown_tables) - 1:
                            writer.writerow([])
                    else:
                        print(f"Warning: No rows parsed from markdown table {table_idx + 1}")
            else:
                print("\nNo markdown tables found, trying fallback extraction...")
                # Fallback: try to extract markdown from string representation
                ocr_str = str(ocr_response)
                print(f"OCR string length: {len(ocr_str)}")
                
                if '|' in ocr_str:
                    print("Found '|' in string representation, attempting to parse...")
                    # Extract markdown table from the string
                    # Look for the markdown content between quotes or after markdown=
                    # Try multiple patterns to find markdown content
                    markdown_content = None
                    
                    # Pattern 1: markdown="content"
                    markdown_match = re.search(r'markdown="([^"]+)"', ocr_str, re.DOTALL)
                    if markdown_match:
                        markdown_content = markdown_match.group(1)
                    else:
                        # Pattern 2: markdown='content'
                        markdown_match = re.search(r"markdown='([^']+)'", ocr_str, re.DOTALL)
                        if markdown_match:
                            markdown_content = markdown_match.group(1)
                    
                    if markdown_content:
                        # Handle escaped newlines and other escape sequences
                        markdown_content = markdown_content.replace('\\n', '\n').replace('\\t', '\t')
                        print(f"Found markdown in string, length: {len(markdown_content)}")
                        print(f"First 300 chars: {markdown_content[:300]}")
                        rows = parse_markdown_table(markdown_content)
                        if rows:
                            for row in rows:
                                writer.writerow(row)
                        else:
                            # Try parsing the full string
                            lines = ocr_str.split('\n')
                            rows = []
                            for line in lines:
                                if '|' in line and line.strip().startswith('|') and line.strip().endswith('|'):
                                    if not all(c in '| -:' for c in line.replace(' ', '')):
                                        cells = [cell.strip() for cell in line.split('|') if cell.strip()]
                                        if cells:
                                            rows.append(cells)
                            if rows:
                                for row in rows:
                                    writer.writerow(row)
                            else:
                                writer.writerow(['OCR Markdown Content'])
                                writer.writerow([ocr_str])
                    else:
                        # Try parsing the full string for table rows
                        lines = ocr_str.split('\n')
                        rows = []
                        for line in lines:
                            if '|' in line and line.strip().startswith('|') and line.strip().endswith('|'):
                                if not all(c in '| -:' for c in line.replace(' ', '')):
                                    cells = [cell.strip() for cell in line.split('|') if cell.strip()]
                                    if cells:
                                        rows.append(cells)
                        if rows:
                            print(f"Found {len(rows)} rows in string representation")
                            for row in rows:
                                writer.writerow(row)
                        else:
                            # Last resort: save as single column with full markdown
                            writer.writerow(['OCR Markdown Content'])
                            writer.writerow([ocr_str])
                else:
                    # Save raw response info
                    writer.writerow(['OCR Response'])
                    writer.writerow([str(ocr_response)])
        
        print(f"\nCSV file saved successfully: {csv_filename}")
        
    except Exception as csv_error:
        print(f"Error converting to CSV: {csv_error}")
        print("Attempting to save raw response as JSON...")
        try:
            json_filename = "ocr_output_page_17.json"
            with open(json_filename, 'w', encoding='utf-8') as jsonfile:
                if isinstance(ocr_response, dict):
                    json.dump(ocr_response, jsonfile, indent=2, ensure_ascii=False, default=str)
                else:
                    json.dump(json.loads(json.dumps(ocr_response, default=str)), jsonfile, indent=2, ensure_ascii=False)
            print(f"Raw response saved as JSON: {json_filename}")
        except Exception as json_error:
            print(f"Error saving JSON: {json_error}")
    
except Exception as e:
    print(f"Error processing OCR: {e}")
    print("\nNote: If you see an API format error, the document format might need adjustment.")
    print("Check Mistral OCR API documentation for the correct format.")
    raise