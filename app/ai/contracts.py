import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CoachStatus = Literal["on_track", "recovering", "watch", "at_risk"]
FactUnit = Literal["EGP", "days", "ratio"]


class VerifiedFinancialFact(BaseModel):
    """One backend-owned value that an explanation may reference."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fact_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1, max_length=100)
    value: float
    unit: FactUnit


class CoachExplanationRequest(BaseModel):
    """Trusted context supplied to a future LLM provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    prompt_version: Literal["budget-coach-v3"] = "budget-coach-v3"
    cycle_id: int = Field(gt=0)
    as_of_date: date
    status: CoachStatus
    facts: tuple[VerifiedFinancialFact, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def fact_ids_must_be_unique(self):
        fact_ids = [fact.fact_id for fact in self.facts]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("Financial fact IDs must be unique")
        return self


class CoachExplanation(BaseModel):
    """Validated output produced by fallback logic or a future LLM."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    source: Literal["deterministic_fallback", "local_response", "llm"]
    prompt_version: Literal["budget-coach-v3"] = "budget-coach-v3"
    headline: str = Field(min_length=1, max_length=100)
    explanation: str = Field(min_length=1, max_length=700)
    recommended_action: str = Field(min_length=1, max_length=300)
    fact_ids_used: tuple[str, ...] = ()
    affects_financial_decisions: Literal[False] = False

    @model_validator(mode="after")
    def llm_answers_must_cite_verified_facts(self):
        if self.source == "llm" and not self.fact_ids_used:
            raise ValueError("LLM explanations must cite a verified fact")
        return self


_EGP_AMOUNT = re.compile(
    r"\bEGP\s+(-?\d[\d,]*(?:\.\d{1,2})?)\b",
    re.IGNORECASE,
)
_DAY_AMOUNT = re.compile(
    r"\b(-?\d+(?:\.\d+)?)\s+days?\b",
    re.IGNORECASE,
)
_PERCENT_AMOUNT = re.compile(r"\b(-?\d+(?:\.\d+)?)\s*%")


def _validate_unit_values(
    combined_text: str,
    request: CoachExplanationRequest,
) -> None:
    """Reject financial quantities not present in backend-owned facts."""

    patterns_and_allowed_values = (
        (
            "EGP",
            _EGP_AMOUNT,
            {
                round(fact.value, 2)
                for fact in request.facts
                if fact.unit == "EGP"
            },
        ),
        (
            "days",
            _DAY_AMOUNT,
            {
                round(fact.value, 2)
                for fact in request.facts
                if fact.unit == "days"
            },
        ),
        (
            "%",
            _PERCENT_AMOUNT,
            {
                value
                for fact in request.facts
                if fact.unit == "ratio"
                for value in (
                    round(fact.value, 2),
                    round(fact.value * 100, 2),
                )
            },
        ),
    )
    for unit, pattern, allowed_values in patterns_and_allowed_values:
        mentioned_values = {
            round(float(match.replace(",", "")), 2)
            for match in pattern.findall(combined_text)
        }
        invented_values = mentioned_values - allowed_values
        if invented_values:
            if unit == "EGP":
                formatted = ", ".join(
                    f"EGP {value:.2f}"
                    for value in sorted(invented_values)
                )
                raise ValueError(
                    f"Explanation introduced unverified amounts: {formatted}"
                )
            formatted = ", ".join(
                f"{value:.2f} {unit}" for value in sorted(invented_values)
            )
            raise ValueError(
                f"Explanation introduced unverified values: {formatted}"
            )


def validate_explanation_against_facts(
    request: CoachExplanationRequest,
    explanation: CoachExplanation,
) -> None:
    """Reject unknown citations and EGP amounts not supplied by the backend."""

    facts_by_id = {fact.fact_id: fact for fact in request.facts}
    unknown_ids = set(explanation.fact_ids_used) - set(facts_by_id)
    if unknown_ids:
        raise ValueError(
            "Explanation cited unknown financial facts: "
            + ", ".join(sorted(unknown_ids))
        )

    display_fields = [
        explanation.headline,
        explanation.explanation,
        explanation.recommended_action,
    ]
    combined_text = " ".join(
        display_fields
    )
    normalized_text = combined_text.lower()
    leaked_fact_ids = {
        fact_id
        for fact_id in facts_by_id
        if re.search(rf"\b{re.escape(fact_id.lower())}\b", normalized_text)
    }
    if re.search(r"\bfact[\s_-]*id\b", normalized_text) or leaked_fact_ids:
        raise ValueError(
            "Explanation exposed internal financial fact identifiers"
        )

    _validate_unit_values(combined_text, request)
