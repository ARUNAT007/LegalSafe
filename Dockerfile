FROM python:3.10-slim

WORKDIR /app
COPY . /app

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    tesseract-ocr \
    poppler-utils \
    && pip install --upgrade pip \
    && pip install -r requirements.txt \
    && python -m spacy download en_core_web_sm

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
