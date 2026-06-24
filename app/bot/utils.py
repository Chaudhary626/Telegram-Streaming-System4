"""Helpers for slugs and filename metadata parsing."""
from __future__ import annotations

import re

_SLUG_RE = re.compile(r"[^a-z0-9]+")

# Known language keywords -> canonical label.
_LANGUAGES = {
    "hindi": "Hindi",
    "hin": "Hindi",
    "english": "English",
    "eng": "English",
    "tamil": "Tamil",
    "telugu": "Telugu",
    "punjabi": "Punjabi",
    "bengali": "Bengali",
    "urdu": "Urdu",
    "dual": "Dual Audio",
}

_QUALITY_RE = re.compile(r"(\d{3,4})\s*p", re.IGNORECASE)


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = _SLUG_RE.sub("-", text)
    return text.strip("-") or "item"


def parse_language(name: str | None) -> str:
    if not name:
        return "original"
    low = name.lower()
    for key, label in _LANGUAGES.items():
        if re.search(rf"\b{re.escape(key)}\b", low):
            return label
    return "original"


def parse_quality(name: str | None) -> str:
    if not name:
        return "auto"
    m = _QUALITY_RE.search(name)
    if m:
        return f"{m.group(1)}p"
    return "auto"


def human_size(num: int) -> str:
    value = float(num)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TB"
