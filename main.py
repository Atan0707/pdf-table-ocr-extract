import boto3
import os
import json
import csv
import glob
from datetime import datetime
from dotenv import load_dotenv
from pypdf import PdfReader, PdfWriter
from io import BytesIO, StringIO

# Load environment variables from .env file
load_dotenv()

# PDF folder path
pdf_folder = "pdf"
# Output folder for CSV files
output_folder = "output"

def find_pdf_files(folder_path):
    """Find all PDF files in the specified folder"""
    pdf_pattern = os.path.join(folder_path, "*.pdf")
    pdf_files = glob.glob(pdf_pattern)
    return pdf_files

def get_text_from_block(blocks_dict, block_id):
    """Extract text from a block by following CHILD relationships to WORD blocks"""
    if block_id not in blocks_dict:
        return ''
    
    block = blocks_dict[block_id]
    text_parts = []
    
    # Check if it's a WORD block directly
    if block.get('BlockType') == 'WORD':
        return block.get('Text', '')
    
    # Follow CHILD relationships
    for relationship in block.get('Relationships', []):
        if relationship['Type'] == 'CHILD':
            for child_id in relationship['Ids']:
                child_text = get_text_from_block(blocks_dict, child_id)
                if child_text:
                    text_parts.append(child_text)
    
    return ' '.join(text_parts)

def extract_table_data(blocks, table_block):
    """
    Extract table data from Textract response following AWS documentation structure.
    Handles merged cells, table titles, footers, and column headers.
    Reference: https://docs.aws.amazon.com/textract/latest/dg/how-it-works-tables.html
    """
    # Create a dictionary for quick block lookup
    blocks_dict = {block['Id']: block for block in blocks}
    
    # Extract table metadata
    entity_types = table_block.get('EntityTypes', [])
    table_type = entity_types[0] if entity_types else 'UNKNOWN'
    
    # Get all cell IDs from CHILD relationships
    cell_ids = []
    merged_cell_ids = []
    title_ids = []
    footer_ids = []
    
    for relationship in table_block.get('Relationships', []):
        rel_type = relationship['Type']
        if rel_type == 'CHILD':
            cell_ids.extend(relationship['Ids'])
        elif rel_type == 'MERGED_CELL':
            merged_cell_ids.extend(relationship['Ids'])
        elif rel_type == 'TABLE_TITLE':
            title_ids.extend(relationship['Ids'])
        elif rel_type == 'TABLE_FOOTER':
            footer_ids.extend(relationship['Ids'])
    
    # Extract table title text
    table_title = ''
    for title_id in title_ids:
        if title_id in blocks_dict:
            title_text = get_text_from_block(blocks_dict, title_id)
            if title_text:
                table_title = title_text
                break
    
    # Extract table footer text
    table_footer = ''
    for footer_id in footer_ids:
        if footer_id in blocks_dict:
            footer_text = get_text_from_block(blocks_dict, footer_id)
            if footer_text:
                table_footer = footer_text
                break
    
    # Process merged cells first to get their text
    merged_cells_data = {}
    for merged_cell_id in merged_cell_ids:
        if merged_cell_id in blocks_dict:
            merged_block = blocks_dict[merged_cell_id]
            row_index = merged_block.get('RowIndex', 0)
            col_index = merged_block.get('ColumnIndex', 0)
            row_span = merged_block.get('RowSpan', 1)
            col_span = merged_block.get('ColumnSpan', 1)
            
            # Extract text from merged cell
            merged_text = get_text_from_block(blocks_dict, merged_cell_id)
            
            # Store merged cell info
            merged_cells_data[(row_index, col_index)] = {
                'text': merged_text,
                'row_span': row_span,
                'col_span': col_span
            }
    
    # Create a dictionary of cells by their row and column indices
    cells = {}
    cell_metadata = {}
    
    for cell_id in cell_ids:
        if cell_id in blocks_dict:
            cell_block = blocks_dict[cell_id]
            if cell_block.get('BlockType') == 'CELL':
                row_index = cell_block.get('RowIndex', 0)
                col_index = cell_block.get('ColumnIndex', 0)
                row_span = cell_block.get('RowSpan', 1)
                col_span = cell_block.get('ColumnSpan', 1)
                entity_types = cell_block.get('EntityTypes', [])
                
                # Check if this cell is part of a merged cell we already processed
                # If so, use the merged cell text
                merged_text = None
                for (m_row, m_col), merged_info in merged_cells_data.items():
                    if (m_row <= row_index < m_row + merged_info['row_span'] and
                        m_col <= col_index < m_col + merged_info['col_span']):
                        merged_text = merged_info['text']
                        break
                
                if merged_text is not None:
                    cell_text = merged_text
                else:
                    # Extract text from cell
                    cell_text = get_text_from_block(blocks_dict, cell_id)
                
                cells[(row_index, col_index)] = cell_text
                cell_metadata[(row_index, col_index)] = {
                    'row_span': row_span,
                    'col_span': col_span,
                    'entity_types': entity_types
                }
    
    # Find max row and column indices
    if not cells:
        return {
            'table_data': [],
            'table_title': table_title,
            'table_footer': table_footer,
            'table_type': table_type,
            'metadata': {}
        }
    
    max_row = max(row for row, col in cells.keys())
    max_col = max(col for row, col in cells.keys())
    
    # Build table as list of rows
    table_data = []
    for row in range(1, max_row + 1):
        row_data = []
        for col in range(1, max_col + 1):
            cell_text = cells.get((row, col), '')
            row_data.append(cell_text)
        table_data.append(row_data)
    
    return {
        'table_data': table_data,
        'table_title': table_title,
        'table_footer': table_footer,
        'table_type': table_type,
        'metadata': {
            'rows': max_row,
            'columns': max_col,
            'merged_cells': len(merged_cells_data),
            'cell_metadata': cell_metadata
        }
    }

def format_table_as_csv(table_info, include_metadata=True):
    """
    Format table data as CSV string.
    Optionally includes metadata rows (title/footer) as separate rows.
    """
    output = StringIO()
    writer = csv.writer(output)
    
    # Add table title as metadata row if present and requested
    if include_metadata and table_info.get('table_title'):
        writer.writerow(['[TABLE_TITLE]', table_info['table_title']])
    
    # Write table data
    table_data = table_info.get('table_data', [])
    for row in table_data:
        writer.writerow(row)
    
    # Add table footer as metadata row if present and requested
    if include_metadata and table_info.get('table_footer'):
        writer.writerow(['[TABLE_FOOTER]', table_info['table_footer']])
    
    return output.getvalue()

def get_csv_filename(pdf_path, page_num, table_idx):
    """
    Generate CSV filename based on PDF filename.
    Format: {pdf_basename}-ocr-page-{page}-table-{table_idx}.csv
    Example: Perangkaan-Agromakanan-Malaysia-2024-ocr-page-17-table-1.csv
    """
    # Get base filename without extension
    pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
    return f"{pdf_basename}-ocr-page-{page_num}-table-{table_idx}.csv"

def combine_tables_to_csv(all_tables_data):
    """
    Combine all tables into a single CSV file.
    Clean format suitable for Excel - just titles and table data.
    """
    output = StringIO()
    writer = csv.writer(output)
    
    # Add timestamp at the top
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    writer.writerow(['Generated on', timestamp])
    writer.writerow([])  # Empty row for spacing
    
    for table_info in all_tables_data:
        table_title = table_info.get('title', '')
        table_data = table_info['table_data']
        
        # Add table title as a regular row (no prefix)
        if table_title:
            writer.writerow([table_title])
        
        # Write table data
        for row in table_data:
            writer.writerow(row)
        
        # Add empty row between tables for spacing
        writer.writerow([])
    
    return output.getvalue()

def process_pdf(pdf_path, log_print):
    """
    Process a single PDF file and extract tables from all pages.
    Returns tuple: (success, all_tables_data, all_tables_summary)
    log_print: Function to use for logging (prints to both console and file)
    """
    
    try:
        # Get AWS credentials from environment variables
        aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "")
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        aws_region = os.getenv("AWS_REGION", "us-east-1")  # Default to us-east-1
        
        if not aws_access_key_id or not aws_secret_access_key:
            log_print("Error: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables must be set")
            return False, [], []
        
        # Initialize Textract client
        textract_client = boto3.client(
            'textract',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )
        
        # Read PDF to get total pages
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        
        # Process all pages from 1 to total_pages
        start_page = 1
        end_page = total_pages
        
        log_print(f"Processing all pages: {start_page} to {end_page} (total: {total_pages} pages)")
        log_print("="*60)
        
        pages_processed = 0
        all_tables_data = []  # Store all table data for combined CSV
        all_tables_summary = []  # Track all extracted tables for summary
        
        # Process each page
        for page_num in range(start_page, end_page + 1):
            log_print(f"\n{'='*60}")
            log_print(f"Processing Page {page_num}...")
            log_print(f"{'='*60}")
            
            try:
                # Extract page from PDF (0-indexed, so page_num - 1)
                writer = PdfWriter()
                writer.add_page(reader.pages[page_num - 1])
                
                # Write to bytes buffer
                buffer = BytesIO()
                writer.write(buffer)
                buffer.seek(0)
                
                # Get PDF bytes for Textract
                pdf_bytes = buffer.getvalue()
                
                log_print(f"Calling AWS Textract API for page {page_num}...")
                log_print(f"  PDF size: {len(pdf_bytes)} bytes")
                
                # Call Textract analyze_document API with TABLES feature
                # This is optimized for extracting table structures
                response = textract_client.analyze_document(
                    Document={
                        'Bytes': pdf_bytes
                    },
                    FeatureTypes=['TABLES']
                )
                
                log_print(f"\n=== Table OCR Output for Page {page_num} ===")
                
                blocks = response.get('Blocks', [])
                
                # Find all table blocks
                table_blocks = [block for block in blocks if block.get('BlockType') == 'TABLE']
                
                log_print(f"\n--- Tables Found: {len(table_blocks)} ---")
                
                if not table_blocks:
                    log_print("No tables detected on this page.")
                    # Print full response for debugging
                    log_print("\n--- Full Textract Response ---")
                    log_print(json.dumps(response, indent=2, default=str))
                else:
                    # Process each table
                    for table_idx, table_block in enumerate(table_blocks, 1):
                        log_print(f"\n--- Table {table_idx} ---")
                        
                        # Extract table data with full metadata
                        table_info = extract_table_data(blocks, table_block)
                        table_data = table_info.get('table_data', [])
                        
                        if table_data:
                            metadata = table_info.get('metadata', {})
                            table_type = table_info.get('table_type', 'UNKNOWN')
                            table_title = table_info.get('table_title', '')
                            table_footer = table_info.get('table_footer', '')
                            
                            # Print table information
                            log_print(f"  Table Type: {table_type}")
                            if table_title:
                                log_print(f"  Table Title: {table_title}")
                            if table_footer:
                                log_print(f"  Table Footer: {table_footer}")
                            log_print(f"  Dimensions: {metadata.get('rows', len(table_data))} rows × {metadata.get('columns', len(table_data[0]) if table_data else 0)} columns")
                            if metadata.get('merged_cells', 0) > 0:
                                log_print(f"  Merged Cells: {metadata['merged_cells']}")
                            
                            # Print table as formatted text
                            log_print("\n  --- Table Content ---")
                            for row_idx, row in enumerate(table_data, 1):
                                row_str = " | ".join(str(cell) if cell else "" for cell in row)
                                log_print(f"  Row {row_idx}: {row_str}")
                            
                            # Store table data for combined CSV
                            all_tables_data.append({
                                'page': page_num,
                                'table_index': table_idx,
                                'type': table_type,
                                'title': table_title,
                                'footer': table_footer,
                                'table_data': table_data
                            })
                            
                            # Add to summary
                            all_tables_summary.append({
                                'page': page_num,
                                'table_index': table_idx,
                                'table_name': table_title if table_title else f'Table {table_idx} (Page {page_num})',
                                'type': table_type,
                                'rows': metadata.get('rows', len(table_data)),
                                'columns': metadata.get('columns', len(table_data[0]) if table_data else 0),
                                'merged_cells': metadata.get('merged_cells', 0)
                            })
                            
                            log_print(f"\n  ✓ Table extracted and will be included in combined CSV")
                        else:
                            log_print("  Warning: Could not extract table data")
                            log_print(f"  Table block ID: {table_block.get('Id', 'N/A')}")
                            log_print(f"  Confidence: {table_block.get('Confidence', 'N/A')}")
                
                # Also log block details for debugging
                log_print(f"\n--- Block Statistics ---")
                block_types = {}
                for block in blocks:
                    block_type = block.get('BlockType', 'UNKNOWN')
                    block_types[block_type] = block_types.get(block_type, 0) + 1
                for block_type, count in block_types.items():
                    log_print(f"  {block_type}: {count}")
                
                # Print full response for debugging (can be commented out if too verbose)
                log_print("\n--- Full Textract Response (JSON) ---")
                log_print(json.dumps(response, indent=2, default=str))
                
                pages_processed += 1
                
            except Exception as page_error:
                log_print(f"Error processing page {page_num}: {page_error}")
                import traceback
                log_print(traceback.format_exc())
                continue
        
        log_print(f"\n{'='*60}")
        log_print(f"Processing Complete!")
        log_print(f"Pages processed: {pages_processed}")
        log_print(f"Total tables extracted: {len(all_tables_data)}")
        
        return True, all_tables_data, all_tables_summary
        
    except Exception as e:
        log_print(f"Error: {e}")
        import traceback
        log_print(traceback.format_exc())
        return False, [], []

# Main execution
if __name__ == "__main__":
    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)
    
    # Find all PDF files in the pdf folder
    pdf_files = find_pdf_files(pdf_folder)
    
    if not pdf_files:
        print(f"Error: No PDF files found in '{pdf_folder}' folder")
        exit(1)
    
    print(f"Found {len(pdf_files)} PDF file(s) in '{pdf_folder}' folder")
    
    # Process each PDF file
    for pdf_path in pdf_files:
        pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
        
        # Setup logging to timestamped log file based on PDF filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{pdf_basename}_log_{timestamp}.txt"
        log_file = open(log_filename, 'w', encoding='utf-8')
        
        # Save original print function
        _original_print = print
        
        def log_print(*args, **kwargs):
            """Print to both console and log file"""
            _original_print(*args, **kwargs)
            message = ' '.join(str(arg) for arg in args)
            log_file.write(message + '\n')
            log_file.flush()
        
        log_print(f"\n{'='*80}")
        log_print(f"Processing PDF: {pdf_path}")
        log_print(f"Log file: {log_filename}")
        log_print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log_print(f"{'='*80}")
        
        # Process the PDF
        success, all_tables_data, all_tables_summary = process_pdf(pdf_path, log_print)
        
        if success:
            log_print(f"\n{'='*80}")
            log_print(f"Processing Complete for {pdf_basename}!")
            log_print(f"Total tables extracted: {len(all_tables_data)}")
            log_print(f"Log file saved: {log_filename}")
            
            # Create single combined CSV file with all tables
            if all_tables_data:
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                combined_filename = os.path.join(output_folder, f"{pdf_basename}_{timestamp_str}.csv")
                combined_csv = combine_tables_to_csv(all_tables_data)
                with open(combined_filename, 'w', encoding='utf-8', newline='') as combined_file:
                    combined_file.write(combined_csv)
                log_print(f"✓ Single CSV file saved: {combined_filename}")
            
            # Create summary CSV file listing all table names
            if all_tables_summary:
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                summary_filename = os.path.join(output_folder, f"{pdf_basename}_summary_{timestamp_str}.csv")
                with open(summary_filename, 'w', encoding='utf-8', newline='') as summary_file:
                    writer = csv.DictWriter(summary_file, fieldnames=[
                        'page', 'table_index', 'table_name', 'type', 
                        'rows', 'columns', 'merged_cells'
                    ])
                    writer.writeheader()
                    writer.writerows(all_tables_summary)
                log_print(f"✓ Summary CSV saved: {summary_filename}")
            
            log_print(f"{'='*80}\n")
        else:
            log_print(f"\n{'='*80}")
            log_print(f"Failed to process {pdf_basename}")
            log_print(f"{'='*80}\n")
        
        # Close log file
        log_file.close()

