from app.ai.expense_categorization import (
    ApprovedCategory,
    ApprovedSubcategory,
    ExpenseCategorizationRequest,
    ExpenseCategorizationSuggestion,
    validate_suggestion_against_options,
)


def _normalize(value: str) -> str:
    normalized = "".join(
        character if character.isalnum() else " "
        for character in value.casefold()
    )
    return " ".join(normalized.split())


def remember_expense_categorization(
    cur,
    *,
    user_id: int,
    description: str | None,
    category_id: int,
    subcategory_id: int,
) -> None:
    """Remember the final user-confirmed pair for one exact phrase."""

    memory_key = _normalize(description or "")
    if not memory_key:
        return

    cur.execute(
        """
        INSERT INTO expense_categorization_memory (
            user_id,
            normalized_description,
            category_id,
            subcategory_id,
            confirmation_count,
            updated_at
        )
        VALUES (%s, %s, %s, %s, 1, NOW())
        ON CONFLICT (user_id, normalized_description)
        DO UPDATE SET
            confirmation_count = CASE
                WHEN expense_categorization_memory.category_id = EXCLUDED.category_id
                 AND expense_categorization_memory.subcategory_id = EXCLUDED.subcategory_id
                THEN expense_categorization_memory.confirmation_count + 1
                ELSE 1
            END,
            category_id = EXCLUDED.category_id,
            subcategory_id = EXCLUDED.subcategory_id,
            updated_at = NOW()
        """,
        (
            user_id,
            memory_key,
            category_id,
            subcategory_id,
        ),
    )


def suggest_expense_category_from_memory(
    cur,
    *,
    request: ExpenseCategorizationRequest,
    user_id: int,
) -> ExpenseCategorizationSuggestion | None:
    """Return an exact active user-owned match without calling a provider."""

    memory_key = _normalize(request.description)
    if not memory_key:
        return None

    cur.execute(
        """
        SELECT
            categories.id,
            categories.name,
            subcategories.id,
            subcategories.name,
            memory.confirmation_count
        FROM expense_categorization_memory AS memory
        JOIN categories ON categories.id = memory.category_id
        JOIN subcategories ON subcategories.id = memory.subcategory_id
        WHERE memory.user_id = %s
        AND memory.normalized_description = %s
        AND categories.user_id = %s
        AND categories.is_active = TRUE
        AND subcategories.is_active = TRUE
        AND subcategories.category_id = categories.id
        """,
        (user_id, memory_key, user_id),
    )
    row = cur.fetchone()
    if not row:
        return None

    category_id, category_name, subcategory_id, subcategory_name, count = row
    suggestion = ExpenseCategorizationSuggestion(
        source="user_memory",
        category_id=category_id,
        category_name=category_name,
        subcategory_id=subcategory_id,
        subcategory_name=subcategory_name,
        confidence=1.0,
        reason=(
            "Matched your previous confirmed choice"
            if count == 1
            else f"Matched {count} of your previous confirmed choices"
        ),
    )
    validate_suggestion_against_options(request, suggestion)
    return suggestion


def _contains_phrase(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def _name_matches(
    description: str,
    categories: tuple[ApprovedCategory, ...],
) -> list[tuple[ApprovedCategory, ApprovedSubcategory]]:
    matches = []
    for category in categories:
        for subcategory in category.subcategories:
            normalized_name = _normalize(subcategory.name)
            if not normalized_name:
                continue
            if _contains_phrase(description, normalized_name):
                matches.append((category, subcategory))
    return matches


def suggest_expense_category(
    request: ExpenseCategorizationRequest,
) -> ExpenseCategorizationSuggestion | None:
    """Match one user-owned expense type exactly, or decline to guess."""

    description = _normalize(request.description)
    matches = _name_matches(description, request.categories)
    if len(matches) != 1:
        return None

    category, subcategory = matches[0]
    normalized_category = _normalize(category.name)
    normalized_subcategory = _normalize(subcategory.name)
    is_exact_type = description == normalized_subcategory
    includes_parent_context = _contains_phrase(
        description,
        normalized_category,
    )
    if not is_exact_type and not includes_parent_context:
        return None

    suggestion = ExpenseCategorizationSuggestion(
        source="deterministic_rule",
        category_id=category.id,
        category_name=category.name,
        subcategory_id=subcategory.id,
        subcategory_name=subcategory.name,
        confidence=0.98,
        reason=f"Matched your expense type '{subcategory.name}'.",
    )
    validate_suggestion_against_options(request, suggestion)
    return suggestion
