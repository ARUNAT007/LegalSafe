import re
from typing import List, Dict, Any
import spacy
import networkx as nx
from rapidfuzz import fuzz

from models.simplifier import Simplifier
from models.legal_ner import get_ner
from utils.pdf_ocr import extract_text_from_bytes
from utils.canonicalize import canonical_party_name, fuzzy_find_equivalent, normalize_text

nlp = spacy.load("en_core_web_sm")

OBLIGATION_KEYWORDS = [
    "shall", "must", "is required to", "are required to", "will", "agrees to", "undertakes to"
]
PROHIBITION_KEYWORDS = [
    "shall not", "must not", "may not", "is prohibited from", "does not"
]
PERMISSION_KEYWORDS = [
    "may", "is permitted to", "is allowed to"
]
DEADLINE_KEYWORDS = [
    "within", "by", "no later than", "before", "on or before"
]

simplifier = Simplifier()
ner = get_ner()

def run_full_pipeline(file_bytes: bytes, filename: str = "document", retry_limit: int = 2) -> Dict[str, Any]:
    text = extract_text_from_bytes(file_bytes, filename)
    text = preprocess_text(text)
    clauses = segment_clauses(text)
    orig_facts = extract_legal_facts(clauses)
    orig_graph = build_fact_graph(orig_facts)
    constraints = extract_constraints(orig_facts)

    simplified = None
    gen_graph = None

    for attempt in range(retry_limit + 1):
        simplified = simplifier.simplify(text, constraints, attempt=attempt)
        simp_clauses = segment_clauses(simplified)
        gen_facts = extract_legal_facts(simp_clauses)
        gen_graph = build_fact_graph(gen_facts)
        mismatches = verify_graphs(orig_graph, gen_graph)
        if not mismatches:
            status = {"verified": True, "attempts": attempt + 1}
            break
        else:
            status = {"verified": False, "attempts": attempt + 1, "mismatches": mismatches}
            if attempt == retry_limit:
                break

    return {
        "original_text": text[:5000],
        "simplified_text": simplified,
        "verification": status,
        "original_graph": nx.node_link_data(orig_graph),
        "generated_graph": nx.node_link_data(gen_graph)
    }

def preprocess_text(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text

def segment_clauses(text: str) -> List[str]:
    pieces = re.split(r"\n\s*\d+\.\s+", text)
    if len(pieces) <= 1:
        pieces = re.split(r"\n\s*\n", text)
    clauses = []
    for p in pieces:
        p = p.strip()
        if not p:
            continue
        if len(p) > 800:
            doc = nlp(p)
            clauses.extend([sent.text.strip() for sent in doc.sents])
        else:
            clauses.append(p)
    return clauses

def extract_legal_facts(clauses: List[str]) -> List[Dict[str, Any]]:
    facts = []
    for c in clauses:
        doc = nlp(c)
        parties = extract_parties(c, doc)
        obligations = extract_obligations(c)
        permissions = extract_permissions(c)
        prohibitions = extract_prohibitions(c)
        deadlines = extract_deadlines(c)
        amounts = extract_amounts(c)
        if parties or obligations or permissions or prohibitions or deadlines or amounts:
            facts.append({
                "clause": c,
                "parties": parties,
                "obligations": obligations,
                "permissions": permissions,
                "prohibitions": prohibitions,
                "deadlines": deadlines,
                "amounts": amounts
            })
    return facts

def extract_parties(text: str, doc=None):
    parties = set()
    try:
        ents = ner.extract_entities(text)
        for e in ents:
            lab = (e.get("label") or "").upper()
            if lab in {"ORG", "COMPANY", "ORGANIZATION", "PERSON"}:
                parties.add(e.get("text"))
    except Exception:
        pass

    doc = doc or nlp(text)
    for ent in doc.ents:
        if ent.label_ in {"ORG", "PERSON"}:
            parties.add(ent.text)

    for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\s+(?:Party|Company|Corporation|LLC|Inc|Ltd))\b", text):
        parties.add(m.group(1))

    parties = [canonical_party_name(p) for p in parties]
    return list(parties)

def extract_obligations(text: str):
    found = []
    lower = text.lower()
    for kw in OBLIGATION_KEYWORDS:
        if kw in lower:
            found.append(kw)
    return found

def extract_permissions(text: str):
    found = []
    lower = text.lower()
    for kw in PERMISSION_KEYWORDS:
        if kw in lower:
            found.append(kw)
    return found

def extract_prohibitions(text: str):
    found = []
    lower = text.lower()
    for kw in PROHIBITION_KEYWORDS:
        if kw in lower:
            found.append(kw)
    return found

def extract_deadlines(text: str):
    found = []
    for kw in DEADLINE_KEYWORDS:
        if kw in text.lower():
            tokens = re.findall(
                r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December))\b",
                text
            )
            found.extend(tokens)
    return found

def extract_amounts(text: str):
    return re.findall(r"\$\s?\d+(?:,\d{3})*(?:\.\d{2})?", text)

def extract_constraints(facts: List[Dict[str, Any]]) -> Dict[str, Any]:
    constraints = {
        "parties": set(),
        "obligations": [],
        "permissions": [],
        "prohibitions": [],
        "deadlines": [],
        "amounts": []
    }
    for f in facts:
        constraints["parties"].update(f.get("parties", []))
        constraints["obligations"].extend(f.get("obligations", []))
        constraints["permissions"].extend(f.get("permissions", []))
        constraints["prohibitions"].extend(f.get("prohibitions", []))
        constraints["deadlines"].extend(f.get("deadlines", []))
        constraints["amounts"].extend(f.get("amounts", []))

    constraints["parties"] = list(constraints["parties"])
    return constraints

def build_fact_graph(facts: List[Dict[str, Any]]) -> nx.DiGraph:
    g = nx.DiGraph()
    existing_parties = []

    for i, f in enumerate(facts):
        clause_node = f"clause_{i}"
        g.add_node(clause_node, text=f.get("clause"), type="clause")

        for p in f.get("parties", []):
            match = fuzzy_find_equivalent(p, existing_parties, threshold=88)
            if match:
                party_node = match
            else:
                party_node = p
                existing_parties.append(party_node)

            if not g.has_node(party_node):
                g.add_node(party_node, type="party", text=party_node)

            g.add_edge(party_node, clause_node, relation="related_to_clause")

        for oi, o in enumerate(f.get("obligations", [])):
            on = f"obligation_{i}_{oi}"
            g.add_node(on, type="obligation", text=o)
            g.add_edge(clause_node, on, relation="has_obligation")

        for di, d in enumerate(f.get("deadlines", [])):
            dn = f"deadline_{i}_{di}"
            g.add_node(dn, type="deadline", text=d)
            g.add_edge(clause_node, dn, relation="has_deadline")

        for ai, a in enumerate(f.get("amounts", [])):
            an = f"amount_{i}_{ai}"
            g.add_node(an, type="amount", text=a)
            g.add_edge(clause_node, an, relation="has_amount")

    return g

def verify_graphs(orig: nx.Graph, gen: nx.Graph) -> List[str]:
    mismatches = []

    orig_parties = [n for n, d in orig.nodes(data=True) if d.get("type") == "party"]
    gen_parties = [n for n, d in gen.nodes(data=True) if d.get("type") == "party"]

    for p in orig_parties:
        if not fuzzy_find_equivalent(p, gen_parties, threshold=85):
            mismatches.append(f"Party missing or changed in simplification: '{p}'")

    orig_obls = [d.get("text") for n, d in orig.nodes(data=True) if d.get("type") == "obligation"]
    gen_obls = [d.get("text") for n, d in gen.nodes(data=True) if d.get("type") == "obligation"]

    for o in orig_obls:
        if o and not any(fuzz.token_set_ratio(o, go) >= 85 for go in gen_obls if go):
            mismatches.append(f"Obligation missing or significantly altered: '{o}'")

    orig_amounts = [d.get("text") for n, d in orig.nodes(data=True) if d.get("type") == "amount"]
    gen_amounts = [d.get("text") for n, d in gen.nodes(data=True) if d.get("type") == "amount"]

    for a in orig_amounts:
        if a and not fuzzy_find_equivalent(a, gen_amounts, threshold=90):
            mismatches.append(f"Amount missing or altered: '{a}'")

    return mismatches
