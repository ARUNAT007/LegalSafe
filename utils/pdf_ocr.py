import io
import pytesseract
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams
from pdf2image import convert_from_bytes


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        output_string = io.StringIO()
        try:
            extract_text_to_fp(io.BytesIO(file_bytes), output_string, laparams=LAParams(), output_type="text", codec=None)
            text = output_string.getvalue().strip()
        except Exception:
            text = ""

        if len(text) < 50:
            try:
                pages = convert_from_bytes(file_bytes, dpi=200)
                ocr_text = []
                for p in pages:
                    ocr_text.append(pytesseract.image_to_string(p))
                text = "\n\n".join(ocr_text)
            except Exception:
                text = ""

        return text

    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return file_bytes.decode("latin-1")
        except Exception:
            return ""
