# PDF-OCR for i-Agri

A Python script to extract text from PDF files using Mistral AI's OCR API. This script processes page 3 of the specified PDF document.

## Prerequisites

- Python 3.7 or higher
- Mistral AI API key

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
pip install mistralai
```

**Note:** Make sure your virtual environment is activated before installing packages. To deactivate the virtual environment later, simply run `deactivate`.

### 3. Set Up Environment Variables

Create a `.env` file in the project root (or set the environment variable):

```bash
export MISTRAL_API_KEY="your-api-key-here"
```

Or create a `.env` file:
```
MISTRAL_API_KEY=your-api-key-here
```

**Note:** The `.env` file is already in `.gitignore` to keep your API key secure.

## How to use

1. **Activate the virtual environment** (if not already activated):
   ```bash
   # macOS/Linux
   source venv/bin/activate
   
   # Windows
   venv\Scripts\activate
   ```

2. Place your PDF file in the `pdf/` directory

3. Update the `pdf_path` variable in `test.py` if your PDF has a different name

4. Run the script:

```bash
python test.py
```

The script will:
- Read the PDF file directly
- Process page 3 with Mistral OCR API using the `page_range` parameter
- Display the extracted text output

## Requirements

See `requirements.txt` for the list of Python dependencies:
- `mistralai` - Mistral AI SDK for OCR processing
