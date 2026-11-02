"""Extractors that turn a clinical note into a validated ``CardioExtraction``.

* ``RuleBasedExtractor``: deterministic regex/lexicon baseline (runs anywhere, used in CI).
* ``LLMExtractor``: schema-constrained LLM extraction with validation and repair retries. It talks
  to any backend implementing ``ChatClient``: a local model through Ollama, or any
  OpenAI-compatible endpoint (OpenAI, vLLM, LM Studio) on a local GPU or in the cloud.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from typing import Protocol

from pydantic import ValidationError

from src.notes.schema import CONDITIONS, MEDICATION_CLASSES, CardioExtraction, Evidence
from src.notes.vocab import MEDICATION_CLASS_INGREDIENTS

# ------------------------------------------------------------------ rule-based baseline

CONDITION_PATTERNS = {
    "hypertension": r"\bhypertension\b",
    "type_2_diabetes": r"diabetes mellitus type 2|type 2 diabetes",
    "prediabetes": r"\bprediabetes\b",
    "hyperlipidemia": r"\bhyperlipidemia\b",
    "chronic_kidney_disease": r"chronic kidney disease|end-stage renal disease",
    "obesity": r"body mass index (30|40)\+|\bobes",
    "ischemic_heart_disease": r"ischemic heart disease",
    "myocardial_infarction": r"myocardial infarction",
    "stroke": r"cerebrovascular accident|\bstroke\b",
    "heart_failure": r"heart failure",
    "atrial_fibrillation": r"atrial fibrillation",
}


def _section(text: str, header: str) -> str:
    m = re.search(rf"# {header}\n(.*?)(?=\n# |\Z)", text, re.S)
    return m.group(1) if m else ""


class RuleBasedExtractor:
    name = "rules"

    def extract(self, text: str) -> CardioExtraction:
        evidence: list[Evidence] = []
        age = sex = None
        m = re.search(r"is an? (\d+) year-old [^.\n]*?\b(male|female)\b", text)
        if m:
            age, sex = int(m.group(1)), m.group(2)
            evidence.append(Evidence(field="age", quote=m.group(0)))

        social = _section(text, "Social History").lower()
        if re.search(r"never smoked", social):
            smoking = "never"
        elif re.search(r"quit smoking|former smoker|ex-smoker", social):
            smoking = "former"
        elif re.search(r"\bsmokes\b|current smoker|is a smoker|every day", social):
            smoking = "current"
        else:
            smoking = "unknown"

        history = (_section(text, "History of Present Illness") + "\n"
                   + _section(text, "Assessment and Plan")).lower()
        conditions = []
        for cond, pat in CONDITION_PATTERNS.items():
            hit = re.search(pat, history)
            if hit:
                conditions.append(cond)
                evidence.append(Evidence(field="conditions", quote=hit.group(0)))

        meds_text = (_section(text, "Medications") + "\n" + _section(text, "Plan")).lower()
        classes = [c for c, names in MEDICATION_CLASS_INGREDIENTS.items()
                   if any(n in meds_text for n in names)]
        return CardioExtraction(age=age, sex=sex, smoking_status=smoking, conditions=conditions,
                                medication_classes=classes, evidence=evidence)


# ------------------------------------------------------------------ LLM extraction

SYSTEM_PROMPT = f"""You extract cardiovascular-relevant facts from one clinical note.
Return ONLY a JSON object matching this schema:
{json.dumps(CardioExtraction.model_json_schema())}

Rules:
- Use only information stated in the note. If a fact is not stated, leave the list empty or use "unknown"/null.
- "conditions": allowed values {list(CONDITIONS)}. Include a condition if the note says the patient has
  or has had it (including in a history list). "history of myocardial infarction" counts as myocardial_infarction.
- "medication_classes": allowed values {list(MEDICATION_CLASSES)}, based on drugs in the medication list.
- "smoking_status": never / former (quit) / current / unknown.
- For every extracted fact add an evidence item whose "quote" is copied verbatim from the note."""


class ChatClient(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class OllamaClient:
    """Local model served by Ollama (e.g. on a workstation GPU). Uses JSON-schema constrained output."""

    def __init__(self, model: str = "llama3.1:8b", host: str = "http://localhost:11434", timeout: int = 300):
        self.model, self.host, self.timeout = model, host.rstrip("/"), timeout

    def complete(self, system: str, user: str) -> str:
        body = {"model": self.model, "stream": False, "options": {"temperature": 0},
                "format": CardioExtraction.model_json_schema(),
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        req = urllib.request.Request(f"{self.host}/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read())["message"]["content"]


class OpenAICompatibleClient:
    """Any OpenAI-compatible chat endpoint: OpenAI, Azure OpenAI, vLLM, LM Studio."""

    def __init__(self, model: str, base_url: str = "https://api.openai.com/v1",
                 api_key: str | None = None, timeout: int = 120):
        self.model, self.base_url, self.timeout = model, base_url.rstrip("/"), timeout
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "not-needed-for-local")

    def complete(self, system: str, user: str) -> str:
        body = {"model": self.model, "temperature": 0, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        req = urllib.request.Request(f"{self.base_url}/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.S)
    if fence:
        raw = fence.group(1)
    start, end = raw.find("{"), raw.rfind("}")
    return json.loads(raw[start:end + 1])


class LLMExtractor:
    """Schema-validated LLM extraction. Invalid output is sent back with the validation error for repair."""

    def __init__(self, client: ChatClient, name: str = "llm", max_retries: int = 2):
        self.client, self.name, self.max_retries = client, name, max_retries
        self.stats = {"calls": 0, "repairs": 0, "failures": 0, "seconds": 0.0}

    def extract(self, text: str) -> CardioExtraction:
        user = f"Clinical note:\n<<<\n{text}\n>>>"
        last_error = ""
        for attempt in range(self.max_retries + 1):
            prompt = user if not last_error else (
                f"{user}\n\nYour previous answer was invalid: {last_error}\nReturn corrected JSON only.")
            t0 = time.perf_counter()
            raw = self.client.complete(SYSTEM_PROMPT, prompt)
            self.stats["seconds"] += time.perf_counter() - t0
            self.stats["calls"] += 1
            try:
                return CardioExtraction.model_validate(_parse_json(raw))
            except (ValueError, ValidationError) as err:
                last_error = str(err)[:800]
                if attempt < self.max_retries:
                    self.stats["repairs"] += 1
        self.stats["failures"] += 1
        return CardioExtraction()  # empty extraction counts as misses, never as a crash
