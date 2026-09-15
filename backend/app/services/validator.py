"""
Second-pass finding validation.

Per the project spec, this validation stage is "important for reducing
false positives": every candidate finding is checked against the diff
and repository context before it's allowed into the final review.

When no LLM provider is configured, we cannot ask a model to validate --
in that case each finding passes through unchanged with
`validated=None` (meaning "not validated", not "validated true"), and
the existing confidence-threshold filter in review_engine.py is the only
safety net. This is documented explicitly rather than silently skipped.
"""
from __future__ import annotations

import logging
from typing import List

from app.llm.base import LLMError, LLMProvider
from app.models.finding import Finding

logger = logging.getLogger("services.validator")


def validate_findings(
    findings: List[Finding],
    diff_context_by_file: dict,
    llm_provider: LLMProvider | None,
) -> List[Finding]:
    """
    Run each finding through the validator. Returns a new list of
    Finding objects with `validated` / `validation_reason` populated.
    Findings the validator rejects (valid=False) are dropped entirely.
    """
    if llm_provider is None:
        for f in findings:
            f.validated = None
            f.validation_reason = "Not validated: no LLM provider configured."
        return findings

    validated: List[Finding] = []
    for finding in findings:
        diff_context = diff_context_by_file.get(finding.file, "")
        try:
            result = llm_provider.validate_finding(diff_context, finding.model_dump(mode="json"))
        except LLMError as exc:
            logger.warning(
                "validator.llm_call_failed",
                extra={"file": finding.file, "error": str(exc)},
            )
            # Fail closed on the LLM side (don't block review) but leave the
            # finding's fate to the existing confidence threshold, clearly
            # marked as unvalidated rather than silently "validated=True".
            finding.validated = None
            finding.validation_reason = f"Validation call failed: {exc}"
            validated.append(finding)
            continue

        is_valid = bool(result.get("valid", False))
        finding.validated = is_valid
        finding.validation_reason = result.get("reason", "")

        if is_valid:
            # The validator's own confidence can further inform (but not
            # replace) the finding's confidence -- take the more
            # conservative (lower) of the two.
            validator_confidence = result.get("confidence")
            if isinstance(validator_confidence, (int, float)):
                finding.confidence = min(finding.confidence, float(validator_confidence))
            validated.append(finding)
        else:
            logger.info(
                "validator.discarded_finding",
                extra={"file": finding.file, "title": finding.title, "reason": finding.validation_reason},
            )

    return validated
