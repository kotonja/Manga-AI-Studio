from __future__ import annotations

import re
from typing import Any

from manga_api.schemas import StyleGuardIssue, StyleGuardResult

RISKY_PHRASES = {
    "make_exactly_like": re.compile(r"\bmake\s+(?:it|this|the\s+style|the\s+art)?\s*exactly\s+like\b", re.IGNORECASE),
    "exactly_like": re.compile(r"\bexactly\s+like\b", re.IGNORECASE),
    "in_the_style_of": re.compile(r"\bin\s+the\s+style\s+of\b", re.IGNORECASE),
    "copy": re.compile(r"\b(copy|copies|copied|copying)\b", re.IGNORECASE),
    "same_as": re.compile(r"\bsame\s+as\b", re.IGNORECASE),
    "clone": re.compile(r"\bclone\b", re.IGNORECASE),
    "indistinguishable": re.compile(r"\bindistinguishable\s+from\b", re.IGNORECASE),
    "one_to_one": re.compile(r"\bone[-\s]?to[-\s]?one\b", re.IGNORECASE),
}

SOFT_REFERENCE_PHRASES = {
    "inspired_by": re.compile(r"\binspired\s+by\b", re.IGNORECASE),
    "similar_to": re.compile(r"\bsimilar\s+to\b", re.IGNORECASE),
}

KNOWN_ARTIST_REFERENCES = [
    "akira toriyama",
    "eiichiro oda",
    "naoko takeuchi",
    "takehiko inoue",
    "kentaro miura",
    "rumiko takahashi",
    "junji ito",
    "clamp",
    "hayao miyazaki",
    "makoto shinkai",
    "masashi kishimoto",
    "tite kubo",
    "hiromu arakawa",
]

KNOWN_FRANCHISE_REFERENCES = [
    "dragon ball",
    "one piece",
    "naruto",
    "bleach",
    "demon slayer",
    "jujutsu kaisen",
    "attack on titan",
    "sailor moon",
    "studio ghibli",
    "chainsaw man",
    "my hero academia",
    "pokemon",
]

AVOIDANCE_FIELDS = {
    "forbidden_references",
    "forbidden_artist_references",
    "forbidden_franchise_references",
    "negative_prompt_fragments",
    "prompt_style_negative",
    "negative_prompts",
    "avoid_keywords",
}


class StyleRiskError(ValueError):
    def __init__(self, result: StyleGuardResult) -> None:
        super().__init__("Style instructions failed originality guard")
        self.result = result


def evaluate_style_safety(payload: dict[str, Any]) -> StyleGuardResult:
    issues: list[StyleGuardIssue] = []
    for field, value in flatten_payload(payload):
        text = str(value).strip()
        if not text:
            continue
        field_root = field.split(".", 1)[0]
        is_avoidance = field_root in AVOIDANCE_FIELDS

        if not is_avoidance:
            for code, pattern in RISKY_PHRASES.items():
                match = pattern.search(text)
                if match:
                    issues.append(
                        StyleGuardIssue(
                            severity="error",
                            code=f"risky_phrase_{code}",
                            message="Style instructions cannot ask to copy or match a specific existing style.",
                            field=field,
                            matched_text=match.group(0),
                        )
                    )

            for artist in KNOWN_ARTIST_REFERENCES:
                if artist in text.casefold():
                    issues.append(
                        StyleGuardIssue(
                            severity="error",
                            code="artist_reference",
                            message="Artist names cannot be used as target style instructions.",
                            field=field,
                            matched_text=artist,
                        )
                    )

            for franchise in KNOWN_FRANCHISE_REFERENCES:
                if franchise in text.casefold():
                    issues.append(
                        StyleGuardIssue(
                            severity="error",
                            code="franchise_reference",
                            message="Franchise names cannot be used as target style instructions.",
                            field=field,
                            matched_text=franchise,
                        )
                    )

        for code, pattern in SOFT_REFERENCE_PHRASES.items():
            match = pattern.search(text)
            if match:
                issues.append(
                    StyleGuardIssue(
                        severity="warning",
                        code=f"soft_reference_{code}",
                        message="Convert references into original visual attributes instead of naming a source.",
                        field=field,
                        matched_text=match.group(0),
                    )
                )

    allowed = not any(issue.severity == "error" for issue in issues)
    severity = "blocked" if not allowed else "warning" if issues else "safe"
    return StyleGuardResult(
        allowed=allowed,
        severity=severity,
        issues=issues,
        suggested_style=suggest_original_style(payload),
    )


def require_style_is_safe(payload: dict[str, Any]) -> StyleGuardResult:
    result = evaluate_style_safety(payload)
    if not result.allowed:
        raise StyleRiskError(result)
    return result


def suggest_original_style(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(payload)
    text_fields = [
        "style_intent",
        "linework",
        "prompt_style_positive",
        "positive_prompt_fragments",
        "face_shape_language",
        "eye_design_language",
        "anatomy_proportions",
    ]
    for field in text_fields:
        if field not in cleaned:
            continue
        value = cleaned[field]
        if isinstance(value, list):
            cleaned[field] = [clean_risky_text(str(item)) for item in value if clean_risky_text(str(item))]
        else:
            cleaned[field] = clean_risky_text(str(value))

    cleaned.setdefault(
        "style_intent",
        "An original manga visual system defined by line behavior, anatomy language, panel rhythm, and tone-specific value design.",
    )
    cleaned.setdefault("positive_prompt_fragments", [])
    if isinstance(cleaned["positive_prompt_fragments"], list):
        cleaned["positive_prompt_fragments"] = [
            *cleaned["positive_prompt_fragments"],
            "original character design language",
            "distinctive line rhythm",
            "consistent panel and lettering system",
        ]
    return cleaned


def clean_risky_text(value: str) -> str:
    cleaned = value
    for pattern in [*RISKY_PHRASES.values(), *SOFT_REFERENCE_PHRASES.values()]:
        cleaned = pattern.sub("with original visual traits shaped by", cleaned)
    for name in [*KNOWN_ARTIST_REFERENCES, *KNOWN_FRANCHISE_REFERENCES]:
        cleaned = re.sub(re.escape(name), "a self-contained original design system", cleaned, flags=re.IGNORECASE)
    return " ".join(cleaned.split())


def flatten_payload(payload: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    flattened: list[tuple[str, Any]] = []
    for key, value in payload.items():
        field = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flattened.extend(flatten_payload(value, field))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                item_field = f"{field}.{index}"
                if isinstance(item, dict):
                    flattened.extend(flatten_payload(item, item_field))
                else:
                    flattened.append((item_field, item))
        else:
            flattened.append((field, value))
    return flattened
