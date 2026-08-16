"""Verificacion de legibilidad de las explicaciones (RNF-04.1).

Implementa una aproximacion del indice de Fernandez-Huerta, la
adaptacion al espanol del test de legibilidad de Flesch. El conteo de
silabas se aproxima contando grupos vocalicos, lo cual es una
heuristica razonable para textos generales en espanol y suficiente
para el proposito de control de calidad de este prototipo academico.
"""

import re

VOWEL_GROUP_RE = re.compile(r"[aeiouáéíóúü]+", re.IGNORECASE)
SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")
WORD_RE = re.compile(r"[a-zA-Záéíóúüñ]+")


def _count_syllables(word: str) -> int:
    groups = VOWEL_GROUP_RE.findall(word)
    return max(1, len(groups))


def fernandez_huerta_score(text: str) -> float:
    """Retorna el indice de legibilidad (mayor = mas facil de leer).

    Rangos orientativos: >90 muy facil, 70-90 facil, 50-70 normal,
    <50 dificil.
    """
    words = WORD_RE.findall(text)
    sentences = [s for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]

    if not words or not sentences:
        return 0.0

    total_syllables = sum(_count_syllables(w) for w in words)
    syllables_per_word = total_syllables / len(words)
    words_per_sentence = len(words) / len(sentences)

    score = 206.84 - 60 * syllables_per_word - 1.02 * words_per_sentence
    return round(score, 2)


def is_readable(text: str, min_score: float = 50.0) -> bool:
    return fernandez_huerta_score(text) >= min_score
