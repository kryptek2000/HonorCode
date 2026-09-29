"""Stylometric feature extraction. Standard library only."""

import re
from collections import Counter

WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

# Function words whose usage rates tend to be habitual per author.
FUNCTION_WORDS = [
    "the", "and", "but", "however", "therefore", "because", "so",
    "very", "really", "just", "also", "although", "while", "since",
    "thus", "moreover", "furthermore", "in", "of", "to",
]

FIRST_PERSON = {"i", "me", "my", "mine", "we", "us", "our", "ours"}


def split_sentences(text):
    """Split text into sentences on . ! ? boundaries."""
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []
    parts = SENT_SPLIT_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def extract(text):
    """Extract a stylometric feature vector from text.

    Returns a dict of feature name -> float. All rates are per-100-words
    unless noted, so texts of different lengths are comparable.
    """
    words = WORD_RE.findall(text.lower())
    raw_words = WORD_RE.findall(text)  # case preserved for caps ratio
    sentences = split_sentences(text)
    paragraphs = [p for p in text.split("\n") if p.strip()]

    n_words = len(words)
    n_sent = len(sentences) if sentences else 1
    if n_words == 0:
        return {name: 0.0 for name in feature_names()}

    counts = Counter(words)
    long_words = sum(1 for w in words if len(w) > 6)
    first_person = sum(counts[w] for w in FIRST_PERSON)
    contractions = sum(1 for w in WORD_RE.findall(text) if "'" in w)
    caps_words = sum(1 for w in raw_words if w.isupper() and len(w) > 1)

    feats = {
        "avg_sentence_len": n_words / n_sent,
        "avg_word_len": sum(len(w) for w in words) / n_words,
        "type_token_ratio": len(counts) / n_words,
        "long_word_ratio": long_words / n_words,
        "first_person_per_100": first_person / n_words * 100,
        "contractions_per_100": contractions / n_words * 100,
        "commas_per_100": text.count(",") / n_words * 100,
        "semicolons_per_100": text.count(";") / n_words * 100,
        "colons_per_100": text.count(":") / n_words * 100,
        "exclaim_per_100": text.count("!") / n_words * 100,
        "question_per_100": text.count("?") / n_words * 100,
        "paragraphs": float(len(paragraphs)),
    }
    for fw in FUNCTION_WORDS:
        feats[f"fw_{fw}_per_100"] = counts.get(fw, 0) / n_words * 100
    return feats


def feature_names():
    """Canonical ordered feature names (stable across runs)."""
    names = [
        "avg_sentence_len", "avg_word_len", "type_token_ratio",
        "long_word_ratio", "first_person_per_100", "contractions_per_100",
        "commas_per_100", "semicolons_per_100", "colons_per_100",
        "exclaim_per_100", "question_per_100", "paragraphs",
    ]
    names += [f"fw_{w}_per_100" for w in FUNCTION_WORDS]
    return names
