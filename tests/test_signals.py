from fda_adcom.analyzer import AnalysisResult
from fda_adcom.signals import generate_signal


def make_analysis(probability: int, confidence: int) -> AnalysisResult:
    return AnalysisResult(
        provider="test",
        overall_sentiment=0,
        approval_probability_estimate=probability,
        confidence=confidence,
        key_concerns=["insufficient evidence"],
        key_positives=[],
        raw={},
    )


def test_low_confidence_is_no_trade() -> None:
    signal = generate_signal(make_analysis(20, 50))
    assert signal.label == "MIXED"
    assert signal.action == "NO_TRADE_REVIEW_MANUALLY"


def test_strong_negative_signal() -> None:
    signal = generate_signal(make_analysis(25, 75))
    assert signal.label == "STRONG_NEGATIVE"


def test_strong_positive_signal() -> None:
    signal = generate_signal(make_analysis(80, 80))
    assert signal.label == "STRONG_POSITIVE"
