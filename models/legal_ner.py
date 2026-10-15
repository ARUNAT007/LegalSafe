"""
Transformer-backed Legal NER with a spaCy fallback.
"""
import os
import logging
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
import spacy

logger = logging.getLogger(__name__)

HF_MODEL = os.environ.get("LEGAL_NER_HF_MODEL", "dslim/bert-base-NER")

class LegalNER:
    def __init__(self):
        self.hf_pipeline = None
        try:
            tokenizer = AutoTokenizer.from_pretrained(HF_MODEL)
            model = AutoModelForTokenClassification.from_pretrained(HF_MODEL)
            self.hf_pipeline = pipeline(
                "token-classification",
                model=model,
                tokenizer=tokenizer,
                aggregation_strategy="simple"
            )
            logger.info(f"Loaded HF legal NER model: {HF_MODEL}")
        except Exception as e:
            logger.warning(f"Could not initialize HF model {HF_MODEL}: {e}. Falling back to spaCy.")
            self.hf_pipeline = None
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except Exception:
                raise

    def extract_entities(self, text: str):
        if self.hf_pipeline:
            try:
                ents = self.hf_pipeline(text)
                normalized = []
                for e in ents:
                    normalized.append({
                        "label": e.get("entity_group") or e.get("entity"),
                        "text": e.get("word") or e.get("entity"),
                        "start": e.get("start"),
                        "end": e.get("end"),
                        "score": e.get("score", 1.0)
                    })
                return normalized
            except Exception as e:
                logger.warning(f"HF pipeline failed: {e}. Falling back to spaCy.")
        doc = self.nlp(text)
        ents = []
        for ent in doc.ents:
            ents.append({
                "label": ent.label_,
                "text": ent.text,
                "start": ent.start_char,
                "end": ent.end_char,
                "score": 1.0
            })
        return ents

_default_ner = None

def get_ner():
    global _default_ner
    if _default_ner is None:
        _default_ner = LegalNER()
    return _default_ner
