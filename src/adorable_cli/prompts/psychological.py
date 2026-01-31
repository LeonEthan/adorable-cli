"""Psychological prompting techniques from Claude Code.

Implements LLM-oriented psychological techniques:
1. Confidence calibration
2. Uncertainty framing
3. Error recovery framing
4. "Never guess" principle
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ConfidenceLevel(Enum):
    """Calibrated confidence levels."""

    CERTAIN = 4      # Verified fact
    HIGH = 3         # Strong evidence
    MODERATE = 2     # Some evidence
    LOW = 1          # Uncertain
    UNKNOWN = 0      # No basis


@dataclass
class CalibratedResponse:
    """A response with calibrated confidence."""

    content: str
    confidence: ConfidenceLevel
    evidence: list[str]
    caveats: list[str]

    def to_prompt_format(self) -> str:
        """Format for inclusion in prompt."""
        parts = [self.content]

        if self.confidence == ConfidenceLevel.LOW:
            parts.append("(Low confidence - verify before acting)")
        elif self.confidence == ConfidenceLevel.MODERATE:
            parts.append("(Moderate confidence - consider alternatives)")

        if self.caveats:
            parts.append(f"Caveats: {'; '.join(self.caveats)}")

        return " ".join(parts)


class ConfidenceCalibrator:
    """Calibrates confidence in agent responses.

    Claude Code insight: "Calibration is easier than elimination."
    Rather than trying to eliminate overconfidence, calibrate it.

    Example:
        calibrator = ConfidenceCalibrator()

        # After a tool result
        calibrated = calibrator.calibrate(
            content="The error is in line 42",
            evidence=["stack trace points to line 42", "variable undefined there"],
            verification_status="confirmed"
        )

        # calibrated.confidence = ConfidenceLevel.HIGH
        # Use this to guide next actions
    """

    def calibrate(
        self,
        content: str,
        evidence: list[str],
        verification_status: str = "unverified",
        contradictions: list[str] | None = None,
    ) -> CalibratedResponse:
        """Calibrate confidence based on evidence.

        Args:
            content: The claim/statement
            evidence: Supporting evidence
            verification_status: "confirmed", "partial", "unverified"
            contradictions: Any contradictory evidence

        Returns:
            Calibrated response
        """
        caveats = []

        # Check for contradictions
        if contradictions:
            confidence = ConfidenceLevel.LOW
            caveats.extend(contradictions)
        # Check verification status
        elif verification_status == "confirmed":
            if len(evidence) >= 2:
                confidence = ConfidenceLevel.CERTAIN
            else:
                confidence = ConfidenceLevel.HIGH
        elif verification_status == "partial":
            confidence = ConfidenceLevel.MODERATE
            caveats.append("Partially verified")
        else:
            # Unverified - check evidence strength
            if len(evidence) >= 3:
                confidence = ConfidenceLevel.MODERATE
            elif len(evidence) >= 1:
                confidence = ConfidenceLevel.LOW
                caveats.append("Not verified")
            else:
                confidence = ConfidenceLevel.UNKNOWN
                caveats.append("No evidence")

        # Additional caveats based on content patterns
        if "probably" in content.lower() or "likely" in content.lower():
            caveats.append("Probabilistic statement")

        if "might" in content.lower() or "may" in content.lower():
            caveats.append("Uncertain possibility")

        return CalibratedResponse(
            content=content,
            confidence=confidence,
            evidence=evidence,
            caveats=caveats,
        )

    def get_confidence_prompt(self, response: CalibratedResponse) -> str:
        """Generate prompt text for confidence level."""
        prompts = {
            ConfidenceLevel.CERTAIN: "Certain. Proceed with confidence.",
            ConfidenceLevel.HIGH: "High confidence. Likely correct.",
            ConfidenceLevel.MODERATE: "Moderate confidence. Verify if critical.",
            ConfidenceLevel.LOW: "Low confidence. Verify before proceeding.",
            ConfidenceLevel.UNKNOWN: "Unknown. Must verify first.",
        }

        base = prompts.get(response.confidence, "Assess confidence.")

        if response.caveats:
            base += f" Caveats: {'; '.join(response.caveats)}"

        return base


class UncertaintyHandler:
    """Handles uncertainty in agent reasoning.

    Key principle: "Never guess" - when uncertain, verify.

    Example:
        handler = UncertaintyHandler()

        # When encountering ambiguity
        guidance = handler.handle_uncertainty(
            situation="Multiple possible file locations",
            options=["src/main.py", "lib/main.py", "app.py"],
            consequences="Editing wrong file breaks app"
        )

        # Returns guidance on how to proceed
    """

    def handle_uncertainty(
        self,
        situation: str,
        options: list[str],
        consequences: str = "",
        allow_guess: bool = False,
    ) -> str:
        """Generate guidance for handling uncertainty.

        Args:
            situation: Description of uncertain situation
            options: Possible options
            consequences: Consequences of wrong choice
            allow_guess: Whether guessing is allowed

        Returns:
            Guidance prompt
        """
        parts = [
            f"UNCERTAIN: {situation}",
            "",
            "Options:",
        ]

        for i, option in enumerate(options, 1):
            parts.append(f"{i}. {option}")

        if consequences:
            parts.extend([
                "",
                f"Risk: {consequences}",
            ])

        if len(options) <= 3 and not allow_guess:
            parts.extend([
                "",
                "DO NOT GUESS. Verify before choosing:",
                "- Use tools to check each option",
                "- Gather more information",
                "- Then decide",
            ])
        elif allow_guess:
            parts.extend([
                "",
                "Best guess acceptable. State confidence.",
            ])
        else:
            parts.extend([
                "",
                "Too many options. Narrow down first.",
            ])

        return "\n".join(parts)

    def get_verification_prompt(self, claim: str) -> str:
        """Get prompt to verify a claim."""
        return f"""VERIFY: {claim}

CRITICAL: Never guess.

Steps:
1. Check with tools
2. Confirm with evidence
3. Then proceed"""

    def get_exploration_prompt(self, goal: str, unknowns: list[str]) -> str:
        """Get prompt for exploring unknown territory."""
        parts = [
            f"EXPLORE: {goal}",
            "",
            "Unknowns:",
        ]

        for unknown in unknowns:
            parts.append(f"- {unknown}")

        parts.extend([
            "",
            "Approach:",
            "1. Gather information",
            "2. Build understanding",
            "3. Then act",
            "",
            "Use think() to plan exploration.",
        ])

        return "\n".join(parts)


class ErrorFraming:
    """Frames errors for productive recovery.

    Claude Code insight: "Prescriptive, not descriptive."
    Tell the model what TO do, not just what went wrong.

    Example:
        framer = ErrorFraming()

        # After a tool error
        prompt = framer.frame_recovery(
            error="Tool 'read_fiel' not found",
            context="Attempting to read config.py",
            attempt_number=1
        )

        # Returns actionable recovery prompt
    """

    def frame_recovery(
        self,
        error: str,
        context: str = "",
        attempt_number: int = 1,
        max_attempts: int = 3,
    ) -> str:
        """Frame an error for recovery.

        Args:
            error: The error message
            context: What was being attempted
            attempt_number: Which attempt this is
            max_attempts: Maximum allowed attempts

        Returns:
            Recovery prompt
        """
        parts = ["RECOVER NOW"]

        if attempt_number >= max_attempts:
            parts.append("Final attempt. Simplify approach.")

        parts.append(f"Error: {error}")

        if context:
            parts.append(f"Context: {context}")

        # Prescriptive guidance based on error type
        parts.extend([
            "",
            "DO THIS:",
        ])

        if "not found" in error.lower() or "unknown" in error.lower():
            parts.extend([
                "1. Check tool name spelling",
                "2. Use exact names from tool list",
                "3. Try again with correct name",
            ])
        elif "argument" in error.lower() or "parameter" in error.lower():
            parts.extend([
                "1. Check required parameters",
                "2. Verify parameter types",
                "3. Fix and retry",
            ])
        elif "format" in error.lower() or "json" in error.lower():
            parts.extend([
                "1. Check JSON syntax",
                "2. Validate structure",
                "3. Try simpler format",
            ])
        elif "permission" in error.lower() or "access" in error.lower():
            parts.extend([
                "1. Check file permissions",
                "2. Verify path exists",
                "3. Try alternative approach",
            ])
        else:
            parts.extend([
                "1. Analyze error cause",
                "2. Fix the issue",
                "3. Continue task",
            ])

        parts.append("\nNo explanation needed. Just fix.")

        return "\n".join(parts)

    def frame_prevention(self, common_error: str) -> str:
        """Frame error prevention guidance."""
        preventions = {
            "tool_hallucination": """PREVENT: Tool Hallucination

ALWAYS: Check tool list first
ALWAYS: Use exact names
NEVER: Invent tool names
NEVER: Combine tool names""",

            "read_before_edit": """PREVENT: Editing Blind

CRITICAL: Read file before editing
CRITICAL: Understand structure first
CRITICAL: Verify after editing""",

            "parameter_error": """PREVENT: Parameter Errors

CHECK: Required parameters
CHECK: Parameter types
VERIFY: Values before sending""",
        }

        return preventions.get(common_error, "Be careful. Verify before acting.")

    def frame_post_error(self, error_type: str, was_recovered: bool) -> str:
        """Frame mindset after error recovery."""
        if was_recovered:
            return """Error recovered. Continue.

Lesson learned. Be vigilant for similar issues."""
        else:
            return f"""Error not resolved.

SIMPLIFY: Break into smaller steps
ALTERNATIVE: Try different approach
VERIFY: Each step before proceeding

Type: {error_type}"""


class CognitiveBiasMitigation:
    """Mitigates common cognitive biases in LLM reasoning.

    Claude Code insights:
    1. Confirmation bias - seeking confirming evidence
    2. Anchoring - over-relying on first information
    3. Overconfidence - certainty without evidence
    """

    @staticmethod
    def confirmation_bias_check(claim: str) -> str:
        """Prompt to check for confirmation bias."""
        return f"""CHECK BIAS: {claim}

Ask:
1. What evidence contradicts this?
2. What other explanations exist?
3. Have I considered alternatives?

NEVER: Cherry-pick supporting evidence"""

    @staticmethod
    def anchoring_mitigation(initial_info: str) -> str:
        """Prompt to mitigate anchoring bias."""
        return f"""ANCHOR CHECK: {initial_info}

Initial info may anchor thinking.

COUNTER:
1. What did I miss?
2. What changed since?
3. Is initial info still valid?"""

    @staticmethod
    def overconfidence_check(confidence: float) -> str:
        """Prompt to check overconfidence."""
        if confidence > 0.8:
            return """OVERCONFIDENCE CHECK

High confidence flagged.

VERIFY:
- Evidence strength
- Alternative explanations
- Unknown unknowns

Confidence without evidence is arrogance."""
        return ""


# Utility functions


def get_never_guess_prompt(question: str) -> str:
    """Generate "never guess" prompt for a question."""
    return f"""Question: {question}

CRITICAL: NEVER GUESS.

If uncertain:
1. State uncertainty clearly
2. Explain what you need to know
3. Request more information
4. OR use tools to verify

Guessing causes errors. Verification prevents them."""


def get_verify_first_prompt(assumption: str) -> str:
    """Generate "verify first" prompt."""
    return f"""Assumption: {assumption}

CRITICAL: Verify before proceeding.

Steps:
1. Check with available tools
2. Confirm assumption holds
3. Then continue

Unverified assumptions cause bugs."""


def get_confidence_prompt(
    claim: str,
    confidence_level: str,
    evidence: list[str],
) -> str:
    """Format a claim with appropriate confidence framing."""
    parts = [f"Claim: {claim}"]

    if confidence_level == "high":
        parts.append("Confidence: High (verified)")
    elif confidence_level == "medium":
        parts.append("Confidence: Medium (some evidence)")
    elif confidence_level == "low":
        parts.append("Confidence: Low (limited evidence)")
        parts.append("Recommendation: Verify before acting")
    else:
        parts.append("Confidence: Unknown")
        parts.append("Recommendation: Must verify first")

    if evidence:
        parts.append(f"Evidence: {'; '.join(evidence[:3])}")

    return "\n".join(parts)
