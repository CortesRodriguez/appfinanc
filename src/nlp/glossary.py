"""Glosario simplificado de terminos financieros (RF-09.2, CU-05)."""

import json
import os

_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "glossary.json")

try:
    with open(_DATA_PATH, encoding="utf-8") as f:
        GLOSSARY_TERMS = json.load(f)
except FileNotFoundError:
    GLOSSARY_TERMS = []


def list_terms():
    return sorted(GLOSSARY_TERMS, key=lambda t: t["term"].lower())


def search_terms(query: str, category: str = ""):
    query = (query or "").strip().lower()
    category = (category or "").strip().lower()
    terms = GLOSSARY_TERMS
    if category:
        terms = [t for t in terms if t.get("category", "").lower() == category]
    if not query:
        return sorted(terms, key=lambda t: t["term"].lower())
    return [t for t in terms if query in t["term"].lower() or query in t["definition"].lower()]
