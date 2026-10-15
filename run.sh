#!/usr/bin/env bash
source .venv/bin/activate || . .venv/Scripts/activate
python -m spacy download en_core_web_sm
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
