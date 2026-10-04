"""Small optional Gemini layer.

The model may extract or phrase text, but it never supplies accepted clinical
values or safety decisions: extraction is validated against patient_variables,
and explanations are checked against the already-produced JSON result.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any

from dietdb.engine.db import connect_readonly
from dietdb.engine.constraints import Patient


DEFAULT_MODEL = "gemini-2.0-flash"
_NUMBER = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


class _GeminiREST:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def _request(self, prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
        request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key})
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode())
        return payload["candidates"][0]["content"]["parts"][0]["text"]

    def generate_json(self, prompt: str) -> dict[str, Any]:
        text = self._request(prompt).strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("Gemini extraction was not a JSON object")
        return value

    def generate_text(self, prompt: str) -> str:
        return self._request(prompt).strip()


def _model(model: Any | None) -> Any | None:
    if model is not None:
        return model
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    return _GeminiREST(key, os.environ.get("GEMINI_MODEL", DEFAULT_MODEL))


def _variables(db: str | Path) -> list[str]:
    with connect_readonly(db) as conn:
        return [r[0] for r in conn.execute("SELECT variable_name FROM patient_variables ORDER BY id")]


def extract_patient(report_text: str, db: str | Path = "data/app.db", model: Any | None = None) -> dict[str, Any]:
    """Extract only explicitly stated patient fields and validate each one."""
    fields = _variables(db)
    client = _model(model)
    if client is None:
        return {"values": {}, "missing_fields": fields, "unknown_fields": [], "rejected_fields": [], "skipped": True}
    prompt = (
        "Return JSON only, with no markdown. Extract only patient variables from this report that are explicitly stated. "
        "Never infer, calculate, normalize, or guess a value. Use these exact field names: "
        f"{json.dumps(fields)}. Omit fields that are not explicitly present. Report text follows:\n{report_text}"
    )
    try:
        raw = client.generate_json(prompt) if hasattr(client, "generate_json") else client.generate(prompt)
    except Exception as exc:
        return {"values": {}, "missing_fields": fields, "unknown_fields": [], "rejected_fields": [],
                "skipped": True, "error": str(exc)}
    if not isinstance(raw, dict):
        return {"values": {}, "missing_fields": fields, "unknown_fields": [], "rejected_fields": [],
                "skipped": True, "error": "model extraction must be a JSON object"}
    accepted: dict[str, Any] = {}
    unknown: list[str] = []
    rejected: list[dict[str, str]] = []
    for name, value in raw.items():
        if name not in fields:
            unknown.append(name)
            continue
        try:
            Patient.from_database({name: value}, str(db))
        except (ValueError, TypeError) as exc:
            rejected.append({"field": name, "reason": str(exc)})
            continue
        accepted[name] = value
    return {"values": accepted, "missing_fields": [f for f in fields if f not in raw],
            "unknown_fields": sorted(unknown), "rejected_fields": rejected, "skipped": False}


def _rationales(result_json: dict[str, Any]) -> str:
    rules = result_json.get("rules_applied") or result_json.get("applied_rules") or []
    text = " ".join(str(r.get("rationale", "")).strip() for r in rules if r.get("rationale"))
    return text or "No rule rationale was provided in the plan result."


def _numbers(value: Any) -> set[float]:
    found: set[float] = set()
    if isinstance(value, dict):
        for item in value.values(): found |= _numbers(item)
    elif isinstance(value, (list, tuple)):
        for item in value: found |= _numbers(item)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        found.update({number, round(number, 1), round(number, 0)})
    elif isinstance(value, str):
        for item in _NUMBER.findall(value):
            found.add(float(item))
    return found


def explain(result_json: dict[str, Any], language: str = "English", model: Any | None = None) -> str:
    """Explain only the supplied result; reject any numeric invention."""
    fallback = _rationales(result_json)
    client = _model(model)
    if client is None:
        return fallback
    payload = json.dumps(result_json, sort_keys=True, ensure_ascii=False)
    prompt = (f"Explain this plan result in plain English{(' and Hindi' if language.lower() == 'hindi' else '')}. "
              "Use only numbers and rule rationale text present in the JSON. Do not add medical advice. "
              "Return prose only. PLAN RESULT JSON:\n" + payload)
    try:
        reply = client.generate_text(prompt) if hasattr(client, "generate_text") else client.generate(prompt)
    except Exception:
        return fallback
    allowed = _numbers(result_json)
    for token in _NUMBER.findall(reply):
        number = float(token)
        if not any(abs(number - candidate) <= 0.1 for candidate in allowed):
            return fallback
    return reply
