from __future__ import annotations

from dataclasses import dataclass

from fda_adcom.analyzer import AnalysisResult


@dataclass(frozen=True)
class Signal:
    label: str
    raw_probability: int
    adjusted_probability: int
    probability: int
    confidence: int
    action: str
    rationale: list[str]
    adjustments_applied: list[str]

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "signal": self.label,
            "raw_probability": self.raw_probability,
            "adjusted_probability": self.adjusted_probability,
            "probability": self.probability,
            "confidence": self.confidence,
            "action": self.action,
            "rationale": self.rationale,
            "adjustments_applied": self.adjustments_applied,
        }


def int_value(analysis: dict, key: str, default: int) -> int:
    try:
        return int(analysis.get(key, default))
    except (TypeError, ValueError):
        return default


def adjust_probability(analysis: dict) -> tuple[int, list[str]]:
    raw_probability = int_value(analysis, "approval_probability_estimate", 50)
    adjusted_probability = raw_probability
    adjustments: list[str] = []

    confidence = int_value(analysis, "confidence", 0)
    if confidence < 60:
        return raw_probability, ["low_confidence_no_adjustment"]

    document_type = str(analysis.get("document_type", "UNKNOWN"))
    unmet_need_score = int_value(analysis, "unmet_need_score", 5)
    regulatory_flexibility = int_value(analysis, "regulatory_flexibility", 5)
    safety_severity = int_value(analysis, "safety_severity", 5)
    safety_manageability = int_value(analysis, "safety_manageability", 5)
    endpoint_met_status = str(analysis.get("endpoint_met_status", "unknown"))
    advisory_question_polarity = str(analysis.get("advisory_question_polarity", "neutral"))
    likely_panel_vote_direction = str(analysis.get("likely_panel_vote_direction", "mixed"))

    if document_type == "FDA_BRIEFING":
        adjusted_probability += 5
        adjustments.append("FDA_BRIEFING de-noising: +5")
    elif document_type == "SPONSOR_BRIEFING":
        adjusted_probability -= 5
        adjustments.append("SPONSOR_BRIEFING optimism discount: -5")

    if unmet_need_score >= 8:
        adjusted_probability += 8
        adjustments.append("high unmet need: +8")

    if regulatory_flexibility >= 8:
        adjusted_probability += 8
        adjustments.append("high regulatory flexibility: +8")

    if safety_severity >= 8 and safety_manageability <= 4:
        adjusted_probability -= 15
        adjustments.append("severe and poorly manageable safety risk: -15")

    if endpoint_met_status in {"failed_primary", "failed_primary_endpoint"}:
        adjusted_probability -= 20
        adjustments.append("failed primary endpoint: -20")

    if endpoint_met_status == "failed_surrogate":
        adjusted_probability -= 12
        adjustments.append("failed surrogate endpoint: -12")

    if advisory_question_polarity == "negative":
        adjusted_probability -= 10
        adjustments.append("negative advisory question polarity: -10")
    elif advisory_question_polarity == "positive":
        adjusted_probability += 5
        adjustments.append("positive advisory question polarity: +5")

    if likely_panel_vote_direction == "positive":
        adjusted_probability += 5
        adjustments.append("likely positive panel vote: +5")
    elif likely_panel_vote_direction == "negative":
        adjusted_probability -= 5
        adjustments.append("likely negative panel vote: -5")

    adjusted_probability = max(0, min(100, adjusted_probability))
    return adjusted_probability, adjustments


def generate_signal(analysis: AnalysisResult) -> Signal:
    analysis_payload = analysis.to_dict()
    raw_probability = int_value(analysis_payload, "approval_probability_estimate", 50)
    adjusted_probability, adjustments = adjust_probability(analysis_payload)
    probability = adjusted_probability
    confidence = analysis.confidence

    if confidence < 60:
        label = "MIXED"
        action = "NO_TRADE_REVIEW_MANUALLY"
    elif probability <= 30:
        label = "STRONG_NEGATIVE"
        action = "REVIEW_PUT_OR_BEARISH_HEDGE"
    elif probability < 45:
        label = "NEGATIVE"
        action = "REVIEW_SMALL_BEARISH_OR_NO_TRADE"
    elif probability >= 75:
        label = "STRONG_POSITIVE"
        action = "REVIEW_CALL_OR_EQUITY_LONG"
    elif probability > 60:
        label = "POSITIVE"
        action = "REVIEW_SMALL_BULLISH_OR_NO_TRADE"
    else:
        label = "MIXED"
        action = "NO_TRADE_REVIEW_MANUALLY"

    rationale = []
    if analysis.key_concerns:
        rationale.append("Concerns: " + "; ".join(analysis.key_concerns[:5]))
    if analysis.key_positives:
        rationale.append("Positives: " + "; ".join(analysis.key_positives[:5]))
    if not rationale:
        rationale.append("Insufficient extracted evidence; manual review required.")

    return Signal(
        label=label,
        raw_probability=raw_probability,
        adjusted_probability=adjusted_probability,
        probability=probability,
        confidence=confidence,
        action=action,
        rationale=rationale,
        adjustments_applied=adjustments,
    )
