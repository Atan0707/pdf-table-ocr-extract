# PDF-OCR for i-Agri

A Python script to extract tables from PDF files using AWS Textract OCR API. This script processes all pages of PDF documents in the `pdf/` folder and extracts table data into CSV files.

## Features

- **Batch Processing**: Automatically processes all PDF files in the `pdf/` folder
- **Full Document Processing**: Extracts tables from all pages of each PDF
- **Table Detection**: Uses AWS Textract's advanced table detection capabilities
- **Merged Cell Support**: Handles merged cells, table titles, and footers
- **CSV Export**: Generates combined CSV files with all extracted tables
- **Summary Reports**: Creates summary CSV files listing all detected tables
- **Detailed Logging**: Generates timestamped log files for each processed PDF

## Prerequisites

- Python 3.7 or higher
- AWS Account with Textract access
- AWS Access Key ID and Secret Access Key

## Installation

### 1. Create and Activate Virtual Environment

It's recommended to use a virtual environment to isolate project dependencies.

#### Create virtual environment:

**macOS/Linux:**
```bash
python3 -m venv venv
```

**Windows:**
```bash
python -m venv venv
```

#### Activate virtual environment:

**macOS/Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```bash
venv\Scripts\activate
```

You should see `(venv)` in your terminal prompt when the virtual environment is active.

### 2. Install Python Dependencies

With the virtual environment activated, install the required Python packages:

```bash
pip install -r requirements.txt
```

Or install individually:
```bash
pip install boto3 python-dotenv pypdf
```

**Note:** Make sure your virtual environment is activated before installing packages. To deactivate the virtual environment later, simply run `deactivate`.

### 3. Set Up AWS Credentials

Create a `.env` file in the project root with your AWS credentials:

```env
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_REGION=us-east-1
```

**Note:** 
- The `.env` file is already in `.gitignore` to keep your credentials secure
- The `AWS_REGION` is optional and defaults to `us-east-1` if not specified
- Make sure your AWS account has Textract permissions enabled

## Project Structure

```
ocr-pdf-iagri/
├── pdf/              # Place your PDF files here
├── output/           # Generated CSV files (created automatically)
├── main.py           # Main script
├── requirements.txt  # Python dependencies
├── .env             # AWS credentials (create this file)
└── README.md        # This file
```

## How to Use

1. **Activate the virtual environment** (if not already activated):
   ```bash
   # macOS/Linux
   source venv/bin/activate
   
   # Windows
   venv\Scripts\activate
   ```

2. **Place your PDF files** in the `pdf/` directory

3. **Run the script**:
   ```bash
   python main.py
   ```

The script will:
- Automatically find all PDF files in the `pdf/` folder
- Process each PDF file page by page
- Extract all tables from each page using AWS Textract
- Generate CSV files in the `output/` folder:
  - `{pdf_name}_{timestamp}.csv` - Combined CSV with all tables
  - `{pdf_name}_summary_{timestamp}.csv` - Summary of all detected tables
- Generate log files in the root directory:
  - `{pdf_name}_log_{timestamp}.txt` - Detailed processing logs

## Output Files

### Combined CSV File
Contains all extracted tables from the PDF, with:
- Table titles
- Table data (rows and columns)
- Empty rows between tables for readability

### Summary CSV File
Contains metadata about all detected tables:
- Page number
- Table index
- Table name/title
- Table type
- Number of rows and columns
- Number of merged cells

### Log File
Contains detailed processing information:
- Page-by-page processing status
- Table detection results
- Full Textract API responses (for debugging)
- Error messages and stack traces (if any)

## Requirements

See `requirements.txt` for the list of Python dependencies:
- `boto3` - AWS SDK for Python (Textract API)
- `python-dotenv` - Environment variable management
- `pypdf` - PDF file manipulation

## Notes

- The script processes all pages of each PDF automatically
- Each run generates new timestamped files (won't overwrite previous results)
- The `output/` folder is created automatically if it doesn't exist
- Processing time depends on PDF size and number of pages
- AWS Textract API charges apply based on pages processed

## Troubleshooting

### Error: AWS credentials not found
- Make sure your `.env` file exists in the project root
- Verify that `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are set correctly

### Error: No PDF files found
- Ensure PDF files are placed in the `pdf/` folder
- Check that PDF files have the `.pdf` extension

### Tables not detected
- Check the log file for detailed Textract responses
- Some PDFs may have tables in image format that require different processing
- Verify that your AWS account has Textract access enabled
