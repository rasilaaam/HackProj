"""Helpers for extracting multilingual aliases from IFCT rows."""

import re


LANGUAGE_NAMES = {
    "A": "Assamese", "B": "Bengali", "G": "Gujarati", "H": "Hindi",
    "Kan": "Kannada", "Kash": "Kashmiri", "Kh": "Khasi", "Kon": "Konkani",
    "Mal": "Malayalam", "M": "Manipuri", "Mar": "Marathi", "N": "Nepali",
    "O": "Oriya", "P": "Punjabi", "S": "Sanskrit", "Tam": "Tamil",
    "Tel": "Telugu", "U": "Urdu", "E": "English",
}


def extract_regional_names(name_field: str) -> dict[str, str]:
    """Return language names from the IFCT ``lang`` field."""
    result: dict[str, str] = {}
    parts = [piece.strip() for piece in name_field.split(";")]
    if parts and not re.match(r"^[A-Za-z]+\.\s*", parts[0]):
        result["English"] = parts.pop(0)
    for part in parts:
        match = re.match(r"^([A-Za-z]+)\.\s*(.+)$", part)
        if match:
            code, alias = match.groups()
            result[LANGUAGE_NAMES.get(code, code)] = alias.strip()
            continue
        match = re.match(r"^([A-Za-z]+)\s*:\s*(.+)$", part)
        if match:
            result[match.group(1)] = match.group(2).strip()
    return result
