from mistralai import Mistral
import os
import base64
import csv
import re
from datetime import datetime
from dotenv import load_dotenv
from pypdf import PdfReader, PdfWriter
from io import BytesIO

# Load environment variables from .env file
load_dotenv()

# PDF file path
pdf_path = "pdf/Perangkaan-Agromakanan-Malaysia-2024.pdf"

# Page number to process (1-indexed)
page_num = 17

# CSV filename
csv_filename = f"ocr_output_page_{page_num}.csv"

# Setup logging to timestamped log file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"log_{timestamp}.txt"
log_file = open(log_filename, 'w', encoding='utf-8')

# Save original print function
_original_print = print

def log_print(*args, **kwargs):
    """Print to both console and log file"""
    # Use original print for console output
    _original_print(*args, **kwargs)
    # Write to log file
    message = ' '.join(str(arg) for arg in args)
    log_file.write(message + '\n')
    log_file.flush()

# Redirect print to log_print
print = log_print

log_print(f"Log file created: {log_filename}")
log_print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
log_print("="*60)

# Load environment variables and initialize client
api_key = os.getenv("MISTRAL_API_KEY", "")
if not api_key:
    log_print("Error: MISTRAL_API_KEY environment variable is not set")
    log_file.close()
    exit(1)

try:
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    
    if page_num < 1 or page_num > total_pages:
        print(f"Error: PDF only has {total_pages} page(s). Page {page_num} does not exist.")
        exit(1)
    
    print(f"Processing page {page_num} of {total_pages}...")
    
    client = Mistral(api_key=api_key)
    
    # Open CSV file for writing (will overwrite if exists)
    csvfile = open(csv_filename, 'w', newline='', encoding='utf-8')
    writer = csv.writer(csvfile)
    
    tables_found = 0
    
    def clean_latex_math(cell_value):
        """Clean LaTeX math formatting from cell values"""
        if not isinstance(cell_value, str):
            return cell_value
        
        # Remove LaTeX math delimiters ($ ... $) - handle empty math blocks first
        # Remove patterns like ${ }^{1}$ or ${ }^{2}$ etc.
        cell_value = re.sub(r'\$\s*\{\s*\}\s*\^\{\d+\}\s*\$', '', cell_value)
        cell_value = re.sub(r'\$\s*\{\s*\}\s*\$', '', cell_value)
        
        # Remove LaTeX math delimiters ($ ... $) - general pattern
        cell_value = re.sub(r'\$([^$]*)\$', r'\1', cell_value)
        
        # Remove \mathbf{...} and other LaTeX commands
        cell_value = re.sub(r'\\mathbf\{([^}]*)\}', r'\1', cell_value)
        cell_value = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', cell_value)
        cell_value = re.sub(r'\\[a-zA-Z]+', '', cell_value)
        
        # Remove remaining LaTeX patterns like { }^{1} or ^{1} (without $ delimiters)
        cell_value = re.sub(r'\{\s*\}\s*\^\{\d+\}', '', cell_value)
        cell_value = re.sub(r'\^\{\d+\}', '', cell_value)
        cell_value = re.sub(r'\{\s*\}', '', cell_value)
        
        # Remove HTML tags like <br>
        cell_value = re.sub(r'<[^>]+>', ' ', cell_value)
        
        # Clean up spaces between digits (e.g., "2 0 2 0" -> "2020")
        # But preserve spaces in text
        def fix_spaced_digits(match):
            digits = match.group(0)
            # Remove spaces between digits
            return re.sub(r'\s+', '', digits)
        
        # Match sequences of digits with spaces between them
        cell_value = re.sub(r'\d(?:\s+\d)+', fix_spaced_digits, cell_value)
        
        # Clean up multiple spaces
        cell_value = re.sub(r'\s+', ' ', cell_value)
        
        # Strip whitespace
        cell_value = cell_value.strip()
        
        return cell_value
    
    def clean_row(row):
        """Clean all cells in a row"""
        return [clean_latex_math(cell) for cell in row]
    
    def remove_duplicate_rows(rows):
        """Remove duplicate and repetitive rows from table data, but only consecutive duplicates"""
        if not rows:
            return rows
        
        # Convert rows to tuples for comparison (after cleaning)
        cleaned_rows = [tuple(clean_row(row)) for row in rows]
        
        # Track result - only remove consecutive duplicates, not duplicates across the table
        result = []
        duplicate_count = 0
        prev_row_tuple = None
        prev_row_count = 0
        
        for i, row_tuple in enumerate(cleaned_rows):
            # Skip empty rows
            if not any(cell.strip() for cell in row_tuple):
                continue
            
            # Check if this is a consecutive duplicate (same as previous row)
            if row_tuple == prev_row_tuple:
                prev_row_count += 1
                # Only skip if we've seen this same row 3+ times consecutively
                if prev_row_count >= 3:
                    duplicate_count += 1
                    continue
                # Otherwise, keep it (might be legitimate repetition in different sections)
                result.append(rows[i])
            else:
                # New row, reset counter
                prev_row_tuple = row_tuple
                prev_row_count = 1
                result.append(rows[i])
        
        # Calculate duplicate percentage
        total_rows = len(rows)
        if total_rows > 0:
            duplicate_percentage = (duplicate_count / total_rows) * 100
            if duplicate_percentage > 30:  # If more than 30% are duplicates
                print(f"  Warning: {duplicate_percentage:.1f}% of rows were consecutive duplicates ({duplicate_count}/{total_rows})")
        
        return result
    
    def extract_table_title(markdown_text):
        """Extract table title from markdown (text immediately before the first table row)"""
        lines = markdown_text.split('\n')
        title_lines = []
        
        # Find the index of the first table row
        first_table_line_idx = None
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if line_stripped.startswith('|'):
                first_table_line_idx = i
                break
        
        if first_table_line_idx is None:
            return None
        
        # Only collect lines immediately before the table (up to 3 lines back, but skip empty lines)
        # Look backwards from the first table line
        collected_lines = []
        for i in range(first_table_line_idx - 1, max(-1, first_table_line_idx - 4), -1):
            line_stripped = lines[i].strip()
            if line_stripped:
                # Skip image references
                if line_stripped.startswith('![') or line_stripped.startswith('img-'):
                    continue
                # Skip markdown headers (#)
                if line_stripped.startswith('#'):
                    continue
                collected_lines.insert(0, line_stripped)
        
        # Filter out lines that don't look like table titles
        # Keep lines that contain table-related keywords or are short (likely titles)
        filtered_lines = []
        for line in collected_lines:
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            
            # Skip very long lines (likely paragraph text, not titles)
            if len(line_stripped) > 200:
                continue
            
            # Keep if it contains table-related keywords (JADUAL, Table, Figure)
            if any(keyword in line_lower for keyword in ['jadual', 'table', 'figure']):
                # For "Figure X:" patterns, extract just the description part
                if line_lower.startswith('figure'):
                    # Extract text after "Figure X:"
                    parts = line_stripped.split(':', 1)
                    if len(parts) > 1:
                        filtered_lines.append(parts[1].strip())
                    else:
                        filtered_lines.append(line_stripped)
                else:
                    filtered_lines.append(line_stripped)
            # Keep short lines (likely titles, not paragraph text)
            elif len(line_stripped) < 200:
                filtered_lines.append(line_stripped)
        
        # If we filtered everything out, use the last collected line (immediately before table)
        if not filtered_lines and collected_lines:
            # Use the last non-empty line immediately before the table
            last_line = collected_lines[-1].strip()
            if len(last_line) < 300:  # Only if it's reasonably short
                filtered_lines = [last_line]
        
        if filtered_lines:
            # Join title lines and clean LaTeX formatting
            title = ' '.join(filtered_lines)
            title = clean_latex_math(title)
            return title
        return None
    
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
                # Check if this continuation line ends with |, meaning the row is complete
                if line_stripped.endswith('|'):
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
    
    def extract_tables_from_ocr_response(ocr_response, page_num):
        """Extract markdown tables from OCR response"""
        markdown_tables = []
        
        # Check if ocr_response has pages attribute
        if hasattr(ocr_response, 'pages'):
            for page in ocr_response.pages:
                if hasattr(page, 'markdown') and page.markdown:
                    markdown_tables.append(page.markdown)
        elif hasattr(ocr_response, '__dict__'):
            ocr_dict = ocr_response.__dict__
            if 'pages' in ocr_dict:
                for page in ocr_dict['pages']:
                    if hasattr(page, 'markdown') and page.markdown:
                        markdown_tables.append(page.markdown)
                    elif isinstance(page, dict) and 'markdown' in page:
                        markdown_tables.append(page['markdown'])
        elif isinstance(ocr_response, dict):
            if 'pages' in ocr_response:
                for page in ocr_response['pages']:
                    if isinstance(page, dict) and 'markdown' in page:
                        markdown_tables.append(page['markdown'])
                    elif hasattr(page, 'markdown'):
                        markdown_tables.append(page.markdown)
        
        return markdown_tables
    
    # Process the single page
    print(f"\n{'='*60}")
    print(f"Processing Page {page_num}...")
    print(f"{'='*60}")
    
    try:
        # Extract page from PDF (0-indexed, so page_num - 1)
        pdf_writer = PdfWriter()
        pdf_writer.add_page(reader.pages[page_num - 1])
        
        # Write to bytes buffer
        buffer = BytesIO()
        pdf_writer.write(buffer)
        buffer.seek(0)
        
        # Convert PDF page to base64
        pdf_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # Process with Mistral OCR
        print(f"Calling OCR API for page {page_num}...")
        print(f"  Request details:")
        print(f"    Model: mistral-ocr-latest")
        print(f"    Document type: document_url")
        print(f"    PDF size: {len(pdf_base64)} base64 characters")
        
        # Call OCR API directly
        ocr_response = client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{pdf_base64}",
            },
        )
        
        # Log OCR response
        print(f"\n  OCR Response received:")
        print(f"    Response type: {type(ocr_response)}")
        if hasattr(ocr_response, 'model'):
            print(f"    Model used: {ocr_response.model}")
        if hasattr(ocr_response, 'usage_info'):
            print(f"    Usage info: {ocr_response.usage_info}")
        if hasattr(ocr_response, 'pages'):
            print(f"    Number of pages in response: {len(ocr_response.pages)}")
            for idx, page in enumerate(ocr_response.pages):
                print(f"    Page {idx}:")
                if hasattr(page, 'index'):
                    print(f"      Index: {page.index}")
                if hasattr(page, 'markdown'):
                    markdown_len = len(page.markdown) if page.markdown else 0
                    print(f"      Markdown length: {markdown_len} characters")
                    if page.markdown:
                        # Log preview in console
                        preview = page.markdown[:500].replace('\n', '\\n')
                        print(f"      Markdown preview: {preview}...")
                        # Write full markdown to log file
                        log_file.write(f"\n      Full Markdown Content:\n")
                        log_file.write(f"      {'='*60}\n")
                        log_file.write(page.markdown)
                        log_file.write(f"\n      {'='*60}\n")
                        log_file.flush()
                if hasattr(page, 'dimensions'):
                    print(f"      Dimensions: {page.dimensions}")
        
        # Log full response as string (for debugging)
        print(f"\n  Full OCR Response (string representation):")
        print(f"    {str(ocr_response)}")
        print(f"    {'-'*60}")
        
        # Extract markdown tables from response
        markdown_tables = extract_tables_from_ocr_response(ocr_response, page_num)
        
        print(f"\n  Extracted markdown tables: {len(markdown_tables)}")
        for idx, markdown_content in enumerate(markdown_tables):
            print(f"    Table {idx + 1}:")
            print(f"      Length: {len(markdown_content)} characters")
            # Log preview in console
            preview = markdown_content[:300].replace(chr(10), '\\n').replace(chr(13), '')
            print(f"      Preview (first 300 chars): {preview}...")
            # Write full markdown content to log file
            log_file.write(f"\n    Full Markdown Content for Table {idx + 1}:\n")
            log_file.write(f"    {'='*60}\n")
            log_file.write(markdown_content)
            log_file.write(f"\n    {'='*60}\n")
            log_file.flush()
        
        if markdown_tables:
            # Add page header
            writer.writerow([])
            writer.writerow([f"Page {page_num}"])
            writer.writerow([])
            
            # Process each markdown table from this page
            for table_idx, markdown_content in enumerate(markdown_tables):
                print(f"  Processing table {table_idx + 1} from page {page_num}...")
                
                # Extract table title
                table_title = extract_table_title(markdown_content)
                if table_title:
                    print(f"  Table title: {table_title[:100]}...")
                
                # Extract table from markdown
                rows = parse_markdown_table(markdown_content)
                print(f"  Parsed {len(rows)} rows from markdown")
                
                if rows:
                    # Remove duplicate/repetitive rows
                    original_count = len(rows)
                    rows = remove_duplicate_rows(rows)
                    filtered_count = len(rows)
                    
                    if original_count != filtered_count:
                        print(f"  Filtered out {original_count - filtered_count} duplicate rows ({filtered_count} unique rows remaining)")
                    
                    # Skip table if too many rows were filtered (likely bad OCR)
                    if filtered_count == 0:
                        print(f"  Warning: All rows were duplicates, skipping table")
                        continue
                    
                    # Skip table if less than 2 rows remain (not useful)
                    if filtered_count < 2:
                        print(f"  Warning: Only {filtered_count} row(s) remaining after filtering, skipping table")
                        continue
                    
                    tables_found += 1
                    
                    # Write table title if available
                    if table_title:
                        writer.writerow([table_title])
                        writer.writerow([])  # Empty row after title
                    
                    # Write rows to CSV (with LaTeX cleaning)
                    for row in rows:
                        cleaned_row = clean_row(row)
                        writer.writerow(cleaned_row)
                    
                    # Add spacing between tables if multiple tables on same page
                    if table_idx < len(markdown_tables) - 1:
                        # Add 2 empty rows for better spacing between tables
                        writer.writerow([])
                        writer.writerow([])
                else:
                    print(f"  Warning: No rows parsed from markdown table {table_idx + 1} on page {page_num}")
        else:
            print(f"  No tables found on page {page_num}")
        
    except Exception as page_error:
        print(f"Error processing page {page_num}: {page_error}")
        import traceback
        traceback.print_exc()
        # Add error marker to CSV
        writer.writerow([])
        writer.writerow([f"Page {page_num} - ERROR: {str(page_error)}"])
        writer.writerow([])
    
    # Close CSV file
    csvfile.close()
    
    log_print(f"\n{'='*60}")
    log_print(f"Processing Complete!")
    log_print(f"Tables found: {tables_found}")
    log_print(f"CSV file saved: {csv_filename}")
    log_print(f"Log file saved: {log_filename}")
    log_print(f"{'='*60}")
    
    # Close log file
    log_file.close()
    
except Exception as e:
    log_print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    if 'csvfile' in locals():
        csvfile.close()
    if 'log_file' in locals():
        log_file.close()
    raise

