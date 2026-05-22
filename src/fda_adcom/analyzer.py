from __future__ import annotations

import json
import re
from dataclasses import dataclass


NEGATIVE_TERMS = [
    "major safety concern",
    "unable to verify",
    "insufficient evidence",
    "uncertain benefit-risk",
    "limitations of the trial design",
    "not clinically meaningful",
    "additional clinical trial",
    "single trial",
    "integrity of the data",
    "hepatotoxicity",
    "mortality imbalance",
]

POSITIVE_TERMS = [
    "substantial evidence",
    "benefit-risk profile appears favorable",
    "data support approval",
    "robust efficacy",
    "clinically meaningful",
    "statistically significant",
]

HEDGING_TERMS = [
    "may",
    "could",
    "appears",
    "suggests",
    "uncertain",
    "unclear",
    "limited",
    "limitations",
]


@dataclass(frozen=True)
class AnalysisResult:
    provider: str
    overall_sentiment: int | str
    approval_probability_estimate: int
    confidence: int
    key_concerns: list[str]
    key_positives: list[str]
    raw: dict
    document_type: str = "UNKNOWN"
    evidence_strength: int = 5
    endpoint_met_status: str = "unknown"
    safety_severity: int = 5
    safety_manageability: int = 5
    unmet_need_score: int = 5
    regulatory_flexibility: int = 5
    advisory_question_polarity: str = "neutral"
    likely_panel_vote_direction: str = "mixed"
    final_approval_vs_adcom_distinction: str = ""
    evidence_notes: list[str] | None = None
    questions_framing: str = ""
    misread_risk: str = ""

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "document_type": self.document_type,
            "overall_sentiment": self.overall_sentiment,
            "approval_probability_estimate": self.approval_probability_estimate,
            "confidence": self.confidence,
            "evidence_strength": self.evidence_strength,
            "endpoint_met_status": self.endpoint_met_status,
            "safety_severity": self.safety_severity,
            "safety_manageability": self.safety_manageability,
            "unmet_need_score": self.unmet_need_score,
            "regulatory_flexibility": self.regulatory_flexibility,
            "advisory_question_polarity": self.advisory_question_polarity,
            "likely_panel_vote_direction": self.likely_panel_vote_direction,
            "final_approval_vs_adcom_distinction": self.final_approval_vs_adcom_distinction,
            "key_concerns": self.key_concerns,
            "key_positives": self.key_positives,
            "evidence_notes": self.evidence_notes or [],
            "questions_framing": self.questions_framing,
            "misread_risk": self.misread_risk,
            "raw": self.raw,
        }


def count_terms(text: str, terms: list[str]) -> dict[str, int]:
    lower = text.lower()
    return {term: lower.count(term) for term in terms if lower.count(term)}


def heuristic_analyze(sections: dict[str, str]) -> AnalysisResult:
    combined = "\n".join(sections.get(name, "") for name in ["executive_summary", "efficacy", "safety", "questions"])
    negative_hits = count_terms(combined, NEGATIVE_TERMS)
    positive_hits = count_terms(combined, POSITIVE_TERMS)
    hedging_hits = count_terms(combined, HEDGING_TERMS)

    negative_score = sum(negative_hits.values())
    positive_score = sum(positive_hits.values())
    sentiment = max(-10, min(10, (positive_score * 2) - (negative_score * 2)))
    probability = max(5, min(95, 50 + sentiment * 4))
    confidence = max(25, min(75, 25 + (positive_score + negative_score) * 5))

    raw = {
        "negative_hits": negative_hits,
        "positive_hits": positive_hits,
        "hedging_hits": hedging_hits,
        "section_lengths": {key: len(value) for key, value in sections.items()},
    }
    return AnalysisResult(
        provider="heuristic",
        document_type="UNKNOWN",
        overall_sentiment=sentiment,
        approval_probability_estimate=probability,
        confidence=confidence,
        evidence_strength=5,
        endpoint_met_status="unknown",
        safety_severity=5,
        safety_manageability=5,
        unmet_need_score=5,
        regulatory_flexibility=5,
        advisory_question_polarity="neutral",
        likely_panel_vote_direction="mixed",
        final_approval_vs_adcom_distinction="",
        key_concerns=sorted(negative_hits, key=negative_hits.get, reverse=True),
        key_positives=sorted(positive_hits, key=positive_hits.get, reverse=True),
        evidence_notes=[],
        questions_framing="",
        misread_risk="",
        raw=raw,
    )


def build_prompt(sections: dict[str, str]) -> str:
    payload = {
        "executive_summary": sections.get("executive_summary", "")[:18_000],
        "efficacy": sections.get("efficacy", "")[:28_000],
        "safety": sections.get("safety", "")[:18_000],
        "questions": sections.get("questions", "")[:10_000],
    }
    return f"""
You are an FDA regulatory affairs and biostatistics reviewer. Analyze this advisory
committee briefing material for regulatory tone and evidence strength.

FDA-authored briefing documents are intentionally critical and risk-focused. Do not
treat harsh tone alone as evidence of likely rejection. Separate:
1. FDA tone
2. clinical evidence
3. endpoint success/failure
4. safety severity
5. safety manageability
6. unmet need
7. regulatory flexibility
8. likely AdCom vote
9. final FDA approval probability

Return only valid JSON with these exact keys:
- document_type: one of FDA_BRIEFING, SPONSOR_BRIEFING, QUESTIONS, BACKGROUND, UNKNOWN
- overall_sentiment: concise string
- approval_probability_estimate: integer from 0 to 100
- confidence: integer from 0 to 100
- evidence_strength: integer from 1 to 10
- endpoint_met_status: one of fully_met, partially_met, failed_primary, failed_surrogate, unknown
- safety_severity: integer from 1 to 10
- safety_manageability: integer from 1 to 10
- unmet_need_score: integer from 1 to 10
- regulatory_flexibility: integer from 1 to 10
- advisory_question_polarity: one of positive, neutral, negative
- likely_panel_vote_direction: one of positive, mixed, negative
- final_approval_vs_adcom_distinction: concise string
- key_concerns: array of concise strings
- key_positives: array of concise strings
- evidence_notes: array of concise strings, each tied to a cited phrase from the document
- questions_framing: concise string
- misread_risk: concise string explaining what might cause an AI or human reader to misread this case

Do not provide trading instructions. If evidence is missing, lower confidence.

DOCUMENT_SECTIONS:
{json.dumps(payload, ensure_ascii=False)}
""".strip()


def parse_model_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError("Model did not return JSON")
    return json.loads(match.group(0))


def openai_analyze(sections: dict[str, str], model: str, timeout_seconds: int = 120) -> AnalysisResult:
    from openai import OpenAI

    client = OpenAI(timeout=timeout_seconds)
    response = client.responses.create(model=model or "gpt-4.1", input=build_prompt(sections))
    data = parse_model_json(response.output_text)
    return model_result("openai", data)


def deepseek_analyze(
    sections: dict[str, str],
    model: str,
    api_key: str,
    base_url: str,
    timeout_seconds: int = 120,
) -> AnalysisResult:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_seconds)
    response = client.chat.completions.create(
        model=model or "deepseek-chat",
        messages=[{"role": "user", "content": build_prompt(sections)}],
        max_tokens=2048,
        temperature=0,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    data = parse_model_json(content)
    return model_result("deepseek", data)


def anthropic_analyze(sections: dict[str, str], model: str, timeout_seconds: int = 120) -> AnalysisResult:
    import anthropic

    client = anthropic.Anthropic(timeout=timeout_seconds)
    response = client.messages.create(
        model=model or "claude-3-5-sonnet-latest",
        max_tokens=4096,
        messages=[{"role": "user", "content": build_prompt(sections)}],
    )
    text = "\n".join(block.text for block in response.content if getattr(block, "type", "") == "text")
    data = parse_model_json(text)
    return model_result("anthropic", data)


def model_result(provider: str, data: dict) -> AnalysisResult:
    def int_field(name: str, default: int, low: int = 0, high: int = 100) -> int:
        try:
            value = int(data.get(name, default))
        except (TypeError, ValueError):
            value = default
        return max(low, min(high, value))

    def text_field(name: str, default: str) -> str:
        value = data.get(name, default)
        return str(value if value is not None else default)

    def list_field(name: str) -> list[str]:
        value = data.get(name, [])
        if isinstance(value, list):
            return [str(item) for item in value]
        if value:
            return [str(value)]
        return []

    return AnalysisResult(
        provider=provider,
        document_type=text_field("document_type", "UNKNOWN"),
        overall_sentiment=data.get("overall_sentiment", "unknown"),
        approval_probability_estimate=int_field("approval_probability_estimate", 50),
        confidence=int_field("confidence", 0),
        evidence_strength=int_field("evidence_strength", 5, 1, 10),
        endpoint_met_status=text_field("endpoint_met_status", "unknown"),
        safety_severity=int_field("safety_severity", 5, 1, 10),
        safety_manageability=int_field("safety_manageability", 5, 1, 10),
        unmet_need_score=int_field("unmet_need_score", 5, 1, 10),
        regulatory_flexibility=int_field("regulatory_flexibility", 5, 1, 10),
        advisory_question_polarity=text_field("advisory_question_polarity", "neutral"),
        likely_panel_vote_direction=text_field("likely_panel_vote_direction", "mixed"),
        final_approval_vs_adcom_distinction=text_field(
            "final_approval_vs_adcom_distinction", ""
        ),
        key_concerns=list_field("key_concerns"),
        key_positives=list_field("key_positives"),
        evidence_notes=list_field("evidence_notes"),
        questions_framing=text_field("questions_framing", ""),
        misread_risk=text_field("misread_risk", ""),
        raw=data,
    )


def analyze_sections(
    provider: str,
    model: str,
    sections: dict[str, str],
    deepseek_api_key: str = "",
    deepseek_base_url: str = "https://api.deepseek.com",
    timeout_seconds: int = 120,
) -> AnalysisResult:
    if provider == "openai":
        return openai_analyze(sections, model, timeout_seconds=timeout_seconds)
    if provider == "deepseek":
        if not deepseek_api_key:
            raise ValueError("AI_PROVIDER=deepseek requires DEEPSEEK_API_KEY or Deepseek_API_KEY")
        return deepseek_analyze(
            sections,
            model,
            deepseek_api_key,
            deepseek_base_url,
            timeout_seconds=timeout_seconds,
        )
    if provider == "anthropic":
        return anthropic_analyze(sections, model, timeout_seconds=timeout_seconds)
    return heuristic_analyze(sections)
