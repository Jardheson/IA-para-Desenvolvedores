from __future__ import annotations

import re
from typing import Any

from src.config import settings
from src.errors.app_error import ValidationError

_INJECTION_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"\bignore\b[\s\S]{0,80}\b(instru(c|ç)(o|õ)es|regras|anterior|prévias|anteriores)\b", re.I), 0.6),
    (re.compile(r"\besque(c|ç)a\b[\s\S]{0,80}\b(regras|instru(c|ç)(o|õ)es)\b", re.I), 0.6),
    (re.compile(r"\b(revel[ae]?|mostre|exiba|vaz[ae]?)\b[\s\S]{0,80}\b(chave|api[\s_-]?key|secret|token|credencial|senha|instru(c|ç)(o|õ)es|sistema interno)\b", re.I), 0.8),
    (re.compile(r"\b(você|vc)\s+(agora\s+é|é\s+agora|passa?\s+a\s+ser)\b|system\s*prompt|<<\s*system\s*>>", re.I), 0.5),
    (re.compile(r"<\s*\/?\s*system\s*>", re.I), 0.5),
    (re.compile(r"\bclassifi\w+\b[\s\S]{0,120}\bbaixa\s+prioridad\w*\b", re.I), 0.4),
    (re.compile(r"\bfor(c|ç)e\b|\bsobrescreva\b|\bdesconsidere\b", re.I), 0.4),
]


def score_injection(text: str) -> float:
    score = 0.0
    for pattern, weight in _INJECTION_PATTERNS:
        if pattern.search(text):
            score += weight
    return round(min(score, 1.0), 3)


class InputValidationResult:
    def __init__(
        self,
        valid: bool,
        errors: list[dict[str, Any]] | None = None,
        injection_score: float = 0.0,
        adversarial_detected: bool = False,
    ) -> None:
        self.valid = valid
        self.errors = errors or []
        self.injection_score = injection_score
        self.adversarial_detected = adversarial_detected

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "injection_score": self.injection_score,
            "adversarial_detected": self.adversarial_detected,
        }


def validate_description(description: str) -> InputValidationResult:
    errors: list[dict[str, Any]] = []
    if not description.strip():
        errors.append({"field": "description", "message": "não pode ser vazio"})
    if len(description) > 5000:
        errors.append({"field": "description", "message": "tamanho máximo excedido (5000 caracteres)"})
    if re.search(r"[\x00\x01\x02\x03]", description):
        errors.append({"field": "description", "message": "contém caracteres inválidos (null bytes)"})

    inj_score = score_injection(description)
    adversarial = inj_score >= settings.adversarial_threshold
    if adversarial:
        errors.append({
            "field": "description",
            "message": "padrão de prompt injection detectado",
            "injection_score": inj_score,
        })

    empty_invalid = any("não pode ser vazio" in e.get("message", "") for e in errors)
    size_invalid = any("tamanho máximo" in e.get("message", "") for e in errors)
    byte_invalid = any("caracteres inválidos" in e.get("message", "") for e in errors)
    valid = not (empty_invalid or size_invalid or byte_invalid)

    return InputValidationResult(
        valid=valid,
        errors=errors,
        injection_score=inj_score,
        adversarial_detected=adversarial,
    )


def validate_incident_payload(payload: dict[str, Any]) -> InputValidationResult:
    if not isinstance(payload, dict):
        raise ValidationError("payload deve ser objeto JSON")
    description = payload.get("description", "") or ""
    return validate_description(description)
