"""Glosario simplificado de terminos financieros (RF-09.2, CU-05)."""

import json
import os

_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "glossary.json")

with open(_DATA_PATH, encoding="utf-8") as f:
    GLOSSARY_TERMS = json.load(f)


def list_terms():
    return sorted(GLOSSARY_TERMS, key=lambda t: t["term"].lower())


def search_terms(query: str):
    query = (query or "").strip().lower()
    if not query:
        return list_terms()
    return [t for t in GLOSSARY_TERMS if query in t["term"].lower() or query in t["definition"].lower()]
