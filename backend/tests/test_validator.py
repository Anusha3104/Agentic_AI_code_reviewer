from unittest.mock import MagicMock

from app.llm.base import LLMError
from app.models.finding import Category, Finding, Severity
from app.services.validator import validate_findings


def _finding(confidence=0.9):
    return Finding(
        file="src/auth.py",
        line=10,
        category=Category.SECURITY,
        severity=Severity.HIGH,
        confidence=confidence,
        title="Possible SQL injection",
        description="d",
        impact="i",
        suggestion="s",
    )


def test_no_llm_provider_passes_through_unvalidated():
    findings = [_finding()]
    result = validate_findings(findings, {}, llm_provider=None)
    assert len(result) == 1
    assert result[0].validated is None
    assert "no LLM provider" in result[0].validation_reason


def test_valid_finding_is_kept():
    mock_llm = MagicMock()
    mock_llm.validate_finding.return_value = {"valid": True, "confidence": 0.9, "reason": "real issue"}
    result = validate_findings([_finding()], {}, llm_provider=mock_llm)
    assert len(result) == 1
    assert result[0].validated is True


def test_invalid_finding_is_discarded():
    mock_llm = MagicMock()
    mock_llm.validate_finding.return_value = {"valid": False, "confidence": 0.9, "reason": "not real"}
    result = validate_findings([_finding()], {}, llm_provider=mock_llm)
    assert result == []


def test_validator_confidence_lowers_finding_confidence():
    mock_llm = MagicMock()
    mock_llm.validate_finding.return_value = {"valid": True, "confidence": 0.5, "reason": "somewhat sure"}
    result = validate_findings([_finding(confidence=0.9)], {}, llm_provider=mock_llm)
    assert result[0].confidence == 0.5


def test_validator_confidence_never_raises_original_confidence():
    mock_llm = MagicMock()
    mock_llm.validate_finding.return_value = {"valid": True, "confidence": 0.99, "reason": "very sure"}
    result = validate_findings([_finding(confidence=0.7)], {}, llm_provider=mock_llm)
    assert result[0].confidence == 0.7  # min(0.7, 0.99) == 0.7


def test_llm_error_marks_unvalidated_but_keeps_finding():
    mock_llm = MagicMock()
    mock_llm.validate_finding.side_effect = LLMError("boom")
    result = validate_findings([_finding()], {}, llm_provider=mock_llm)
    assert len(result) == 1
    assert result[0].validated is None
    assert "boom" in result[0].validation_reason
