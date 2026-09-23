from app.ai.contracts import (
    CoachExplanation,
    CoachExplanationRequest,
    VerifiedFinancialFact,
    validate_explanation_against_facts,
)


def build_explanation_request(
    cycle_coach: dict,
) -> CoachExplanationRequest:
    """Convert the live coach response into provider-safe verified facts."""

    position = cycle_coach["financial_position"]
    facts = (
        VerifiedFinancialFact(
            fact_id="remaining_budget",
            label="Remaining cycle budget",
            value=position["remaining_budget"],
            unit="EGP",
        ),
        VerifiedFinancialFact(
            fact_id="remaining_days",
            label="Remaining cycle days",
            value=position["remaining_days"],
            unit="days",
        ),
        VerifiedFinancialFact(
            fact_id="safe_daily_target",
            label="Safe daily spending target",
            value=position["safe_daily_target"],
            unit="EGP",
        ),
        VerifiedFinancialFact(
            fact_id="recent_daily_average",
            label="Recent completed-day spending average",
            value=position["recent_completed_day_average"],
            unit="EGP",
        ),
        VerifiedFinancialFact(
            fact_id="daily_adjustment",
            label="Daily spending reduction needed",
            value=position["daily_adjustment_needed"],
            unit="EGP",
        ),
        VerifiedFinancialFact(
            fact_id="daily_buffer",
            label="Daily buffer below the safe target",
            value=position["daily_buffer"],
            unit="EGP",
        ),
        VerifiedFinancialFact(
            fact_id="cycle_pace_projection",
            label="Projected balance using whole-cycle pace",
            value=position["cycle_pace_projected_end_balance"],
            unit="EGP",
        ),
        VerifiedFinancialFact(
            fact_id="recent_pace_projection",
            label="Projected balance using recent pace",
            value=position["recent_pace_projected_end_balance"] or 0,
            unit="EGP",
        ),
    )
    return CoachExplanationRequest(
        cycle_id=cycle_coach["cycle_id"],
        as_of_date=cycle_coach["as_of_date"],
        status=cycle_coach["status"],
        facts=facts,
    )


def build_fallback_explanation(
    request: CoachExplanationRequest,
) -> CoachExplanation:
    """Provide safe wording before an LLM provider is connected."""

    facts = {fact.fact_id: fact.value for fact in request.facts}
    status = request.status

    if status == "recovering":
        headline = "Your recent spending is recovering"
        explanation = (
            "Your recent completed-day average is EGP "
            f"{facts['recent_daily_average']:.2f}, below the safe daily target "
            f"of EGP {facts['safe_daily_target']:.2f}. Maintaining this pace "
            "could leave approximately EGP "
            f"{facts['recent_pace_projection']:.2f} at cycle end."
        )
        action = (
            "Keep daily spending at or below EGP "
            f"{facts['safe_daily_target']:.2f}."
        )
        used = (
            "recent_daily_average",
            "safe_daily_target",
            "recent_pace_projection",
        )
    elif status in {"watch", "at_risk"}:
        headline = "Your spending pace needs attention"
        explanation = (
            "Your recent completed-day average is EGP "
            f"{facts['recent_daily_average']:.2f}, compared with a safe daily "
            f"target of EGP {facts['safe_daily_target']:.2f}."
        )
        action = (
            "Reduce daily spending by EGP "
            f"{facts['daily_adjustment']:.2f}."
        )
        used = (
            "recent_daily_average",
            "safe_daily_target",
            "daily_adjustment",
        )
    else:
        headline = "Your spending is on track"
        explanation = (
            "Your recent completed-day average is EGP "
            f"{facts['recent_daily_average']:.2f}, within the safe daily target "
            f"of EGP {facts['safe_daily_target']:.2f}."
        )
        action = (
            "Continue keeping daily spending at or below EGP "
            f"{facts['safe_daily_target']:.2f}."
        )
        used = ("recent_daily_average", "safe_daily_target")

    result = CoachExplanation(
        source="deterministic_fallback",
        headline=headline,
        explanation=explanation,
        recommended_action=action,
        fact_ids_used=used,
    )
    validate_explanation_against_facts(request, result)
    return result


def build_unknown_goal_explanation(
    request: CoachExplanationRequest,
    requested_goal_name: str,
    available_goal_names: tuple[str, ...],
) -> CoachExplanation:
    """Explain a failed goal lookup without asking the LLM to improvise."""

    if available_goal_names:
        available = ", ".join(available_goal_names)
        explanation = (
            f"I couldn't find an active goal named {requested_goal_name}. "
            f"Your active goal choices are: {available}."
        )
        action = f"Ask me about {available_goal_names[0]}, or choose another goal."
        goal_fact_ids = tuple(
            fact.fact_id
            for fact in request.facts
            if fact.fact_id.startswith("goal_")
        )
        used = goal_fact_ids[:1] or (request.facts[0].fact_id,)
    else:
        explanation = (
            f"I couldn't find an active goal named {requested_goal_name}, "
            "and there are no active goals available in this cycle."
        )
        action = "Create a goal first, then ask me how to plan for it."
        used = (request.facts[0].fact_id,)

    result = CoachExplanation(
        source="deterministic_fallback",
        headline="I couldn't find that goal",
        explanation=explanation,
        recommended_action=action,
        fact_ids_used=used,
    )
    validate_explanation_against_facts(request, result)
    return result


def build_unsupported_question_explanation(
    request: CoachExplanationRequest,
) -> CoachExplanation:
    """Decline an unrelated question without calling an LLM."""

    result = CoachExplanation(
        source="deterministic_fallback",
        headline="I can help with your Bako finances",
        explanation=(
            "I'm focused on your Bako finances. I can help with your spending, "
            "budget, goals, cards, recommendations, or current cycle."
        ),
        recommended_action=(
            "Tell me what you would like to understand about your Bako budget."
        ),
        fact_ids_used=(),
    )
    validate_explanation_against_facts(request, result)
    return result


def build_conversation_explanation(
    request: CoachExplanationRequest,
    conversation_kind: str,
    first_name: str | None = None,
    language: str = "en",
) -> CoachExplanation:
    """Respond naturally to brief conversation without an LLM call."""

    name = f" {first_name}" if first_name else ""
    if language == "ar":
        if conversation_kind == "thanks":
            headline = f"العفو{name}"
            explanation = "أنا موجود عندما تريد فهم أموالك في Bako."
            action = "اسألني عن المصروفات أو الميزانية أو الأهداف أو البطاقات أو الدورة الحالية."
        elif conversation_kind == "acknowledgement":
            headline = "تمام"
            explanation = "يمكننا المتابعة عندما تكون جاهزاً."
            action = "اسألني سؤالك التالي عن أموالك في Bako."
        elif conversation_kind == "help":
            headline = f"بالتأكيد{name}"
            explanation = (
                "أستطيع مراجعة مصروفات اليوم، أو متابعة معدل الصرف، أو شرح المبلغ "
                "الآمن للصرف، أو مراجعة أحدث توصيات دورتك."
            )
            action = "قل لي ما الذي تريد فهمه أولاً."
        else:
            headline = f"أهلاً{name}"
            explanation = "كيف أساعدك في أموالك اليوم؟"
            action = (
                "أستطيع مراجعة مصروفات اليوم، أو معدل الصرف، أو المبلغ الآمن "
                "للصرف، أو أحدث التوصيات."
            )
    elif conversation_kind == "thanks":
        headline = f"You're welcome{name}"
        explanation = "I'm here whenever you want to understand your Bako finances."
        action = "Ask me about spending, budget pace, goals, cards, or your current cycle."
    elif conversation_kind == "acknowledgement":
        headline = "All right"
        explanation = "We can continue whenever you're ready."
        action = "Ask me your next question about your Bako finances."
    elif conversation_kind == "help":
        headline = f"Of course{name}"
        explanation = (
            "I can review today's spending, check your spending pace, explain "
            "your safe-to-spend amount, or look at your latest cycle recommendations."
        )
        action = "Tell me what you want to understand first."
    else:
        headline = f"Hi{name}"
        explanation = "How can I help with your money today?"
        action = (
            "I can review today's spending, check your spending pace, explain "
            "your safe-to-spend amount, or look at your latest recommendations."
        )

    result = CoachExplanation(
        source="local_response",
        headline=headline,
        explanation=explanation,
        recommended_action=action,
        fact_ids_used=(),
    )
    validate_explanation_against_facts(request, result)
    return result


def build_clarification_explanation(
    request: CoachExplanationRequest,
    available_goal_names: tuple[str, ...],
) -> CoachExplanation:
    """Ask what the user means before proposing or executing an action."""

    if available_goal_names:
        choices = ", ".join(available_goal_names)
        explanation = f"Do you want to add money to one of these goals: {choices}?"
        action = (
            "Reply with the goal name, and I'll calculate what is safe from "
            "your current cycle."
        )
    else:
        explanation = (
            "Do you want to add money to your current cycle budget or create "
            "a new goal?"
        )
        action = (
            "Tell me which one you mean, and I'll guide you without moving "
            "money automatically."
        )

    result = CoachExplanation(
        source="local_response",
        headline="Which place should the money go?",
        explanation=explanation,
        recommended_action=action,
        fact_ids_used=(),
    )
    validate_explanation_against_facts(request, result)
    return result
