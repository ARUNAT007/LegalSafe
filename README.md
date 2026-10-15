# LegalSafe-G

LegalSafe-G is a legal-document simplification prototype that follows the workflow:
- document input
- text extraction
- preprocessing
- clause segmentation
- legal fact extraction
- original legal fact graph construction
- constraint-aware simplification
- generated fact graph
- verification and mismatch detection
- controlled regeneration

## Features
- PDF / text upload
- OCR support via Tesseract + pdf2image
- Clause segmentation
- Legal fact extraction with NER + heuristics
- Fact graph building using NetworkX
- Simplification via OpenAI if API key is present, otherwise a Hugging Face fallback
- Verification with fuzzy matching and cascade regeneration
- Basic web frontend for upload, side-by-side output, and graph visualisation

## Setup
1. Create a venv:
   python -m venv .venv
   source .venv/bin/activate   # Linux/macOS
   .\.venv\Scripts\Activate.ps1   # Windows PowerShell

2. Install requirements:
   pip install -r requirements.txt

3. Install spaCy model:
   python -m spacy download en_core_web_sm

4. (Optional) set API key:
   export OPENAI_API_KEY=...
   # or create a .env file

5. Start the app:
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

6. Open:
   http://127.0.0.1:8000/

## Test with curl
curl -X POST -F "file=@examples/sample_contract.txt" http://127.0.0.1:8000/simplify

## Docker
docker build -t legalsafe-g .
docker run -p 8000:8000 legalsafe-g
