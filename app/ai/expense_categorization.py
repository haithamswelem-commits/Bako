from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ApprovedSubcategory(BaseModel):
    """One backend-approved subcategory that the categorizer may select."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)


class ApprovedCategory(BaseModel):
    """One backend-approved category and its allowed subcategories."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    subcategories: tuple[ApprovedSubcategory, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def subcategory_ids_must_be_unique(self):
        ids = [subcategory.id for subcategory in self.subcategories]
        if len(ids) != len(set(ids)):
            raise ValueError("Subcategory IDs must be unique within a category")
        return self


class ExpenseCategorizationRequest(BaseModel):
    """Trusted choices and untrusted expense text sent to a categorizer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    description: str = Field(min_length=2, max_length=200)
    categories: tuple[ApprovedCategory, ...] = ()

    @field_validator("description")
    @classmethod
    def description_must_contain_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Expense description must contain meaningful text")
        return normalized

    @model_validator(mode="after")
    def category_and_subcategory_ids_must_be_unique(self):
        category_ids = [category.id for category in self.categories]
        if len(category_ids) != len(set(category_ids)):
            raise ValueError("Category IDs must be unique")

        subcategory_ids = [
            subcategory.id
            for category in self.categories
            for subcategory in category.subcategories
        ]
        if len(subcategory_ids) != len(set(subcategory_ids)):
            raise ValueError("Subcategory IDs must be globally unique")
        return self


class ExpenseCategorizationSuggestion(BaseModel):
    """A non-binding category suggestion that the user must confirm."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    source: Literal["deterministic_rule", "user_memory", "llm"]
    category_id: int = Field(gt=0)
    category_name: str = Field(min_length=1, max_length=100)
    subcategory_id: int = Field(gt=0)
    subcategory_name: str = Field(min_length=1, max_length=100)
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=200)
    requires_user_confirmation: Literal[True] = True


class ExpenseCategorizationProposal(BaseModel):
    """A new user-owned pair proposed by the provider but not yet created."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    source: Literal["llm"] = "llm"
    category_name: str = Field(min_length=1, max_length=100)
    subcategory_name: str = Field(min_length=1, max_length=100)
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=200)
    requires_user_confirmation: Literal[True] = True

    @field_validator("category_name", "subcategory_name")
    @classmethod
    def proposed_names_must_be_meaningful(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not any(character.isalpha() for character in normalized):
            raise ValueError("Proposed names must include at least one letter")
        return normalized


class SemanticCategorizationDecision(BaseModel):
    """Structured provider decision before IDs are trusted by the backend."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    matched: bool
    category_id: int | None = Field(default=None, gt=0)
    subcategory_id: int | None = Field(default=None, gt=0)
    proposed_category_name: str | None = Field(default=None, max_length=100)
    proposed_subcategory_name: str | None = Field(default=None, max_length=100)
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def match_fields_must_be_consistent(self):
        ids = (self.category_id, self.subcategory_id)
        proposed_names = (
            self.proposed_category_name,
            self.proposed_subcategory_name,
        )
        if self.matched and any(value is None for value in ids):
            raise ValueError("Matched decisions require both IDs")
        if not self.matched and any(value is not None for value in ids):
            raise ValueError("Unmatched decisions cannot include IDs")
        if self.matched and any(value is not None for value in proposed_names):
            raise ValueError("Matched decisions cannot propose new names")
        if any(value is not None for value in proposed_names) and any(
            value is None for value in proposed_names
        ):
            raise ValueError("Proposals require both names")
        return self


def validate_suggestion_against_options(
    request: ExpenseCategorizationRequest,
    suggestion: ExpenseCategorizationSuggestion,
) -> None:
    """Reject category suggestions that are not in the approved hierarchy."""

    category = next(
        (
            candidate
            for candidate in request.categories
            if candidate.id == suggestion.category_id
        ),
        None,
    )
    if category is None:
        raise ValueError("Suggestion used an unknown category ID")
    if category.name != suggestion.category_name:
        raise ValueError("Suggestion category name does not match its ID")

    subcategory = next(
        (
            candidate
            for candidate in category.subcategories
            if candidate.id == suggestion.subcategory_id
        ),
        None,
    )
    if subcategory is None:
        raise ValueError(
            "Suggestion used an unknown subcategory for the selected category"
        )
    if subcategory.name != suggestion.subcategory_name:
        raise ValueError("Suggestion subcategory name does not match its ID")
