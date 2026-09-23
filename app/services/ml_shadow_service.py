import json
import os
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class MLServiceUnavailableError(RuntimeError):
    pass


def build_canonical_budget_snapshot(
    budget_data: dict,
    as_of_date: date,
) -> dict:
    daily_table = budget_data.get("daily_table", [])
    if not daily_table:
        raise ValueError("Budget table is empty")

    cycle_start_date = daily_table[0]["date"]
    cycle_end_date = daily_table[-1]["date"]
    if not cycle_start_date <= as_of_date <= cycle_end_date:
        raise ValueError("Shadow prediction date must be within the cycle")

    actual_rows = [
        row for row in daily_table
        if row["date"] <= as_of_date and row["status"] == "actual"
    ]

    return {
        "schema_version": "2.0",
        "cycle_id": budget_data["cycle_id"],
        "as_of_date": str(as_of_date),
        "cycle_start_date": str(cycle_start_date),
        "cycle_end_date": str(cycle_end_date),
        "income_amount": budget_data["income"],
        "available_budget": budget_data["available_budget"],
        "remaining_total_budget": budget_data["remaining_total_budget"],
        "remaining_days": budget_data["remaining_days"],
        "total_days": budget_data["total_days"],
        "current_daily_allowance": budget_data[
            "current_daily_allowance"
        ],
        "cumulative_daily_expenses": round(
            sum(row["daily_expenses_today"] for row in actual_rows),
            2,
        ),
        "cumulative_goal_contributions": round(
            sum(row["goal_contributions_today"] for row in actual_rows),
            2,
        ),
    }


def request_budget_risk_prediction(snapshot: dict) -> dict:
    service_url = os.getenv(
        "ML_SERVICE_URL",
        "http://ml-service:8001",
    ).rstrip("/")
    timeout = float(os.getenv("ML_SERVICE_TIMEOUT_SECONDS", "3"))
    request = Request(
        f"{service_url}/v1/predictions/budget-risk",
        data=json.dumps(snapshot).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise MLServiceUnavailableError(
            f"ML service rejected the snapshot: {detail}"
        ) from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise MLServiceUnavailableError(
            "ML service is unavailable"
        ) from error


def build_live_cycle_coach_response(
    budget_data: dict,
    prediction: dict,
    as_of_date: date,
    history_days: int = 5,
) -> dict:
    if not 1 <= history_days <= 30:
        raise ValueError("history_days must be between 1 and 30")

    actual_rows = [
        row
        for row in budget_data.get("daily_table", [])
        if row["date"] <= as_of_date and row["status"] == "actual"
    ]
    if not actual_rows:
        raise ValueError("No daily history is available for this cycle")

    completed_rows = [
        row for row in actual_rows if row["date"] < as_of_date
    ]
    today_row = next(
        (row for row in actual_rows if row["date"] == as_of_date),
        None,
    )
    recent_rows = completed_rows[-history_days:]
    recent_total = round(
        sum(float(row["used_today"]) for row in recent_rows),
        2,
    )
    recent_average = (
        round(recent_total / len(recent_rows), 2)
        if recent_rows
        else 0
    )
    safe_daily_target = round(
        max(float(budget_data["current_daily_allowance"]), 0),
        2,
    )
    daily_adjustment = round(
        max(recent_average - safe_daily_target, 0),
        2,
    )
    daily_buffer = round(
        max(safe_daily_target - recent_average, 0),
        2,
    )

    features = prediction.get("features", {})
    available_budget = float(budget_data["available_budget"])
    cycle_pace_projected_end_balance = round(
        float(features.get("projected_end_balance_ratio", 0))
        * available_budget,
        2,
    )
    risk_probability = float(prediction["overrun_probability"])
    remaining_budget = round(
        float(budget_data["remaining_total_budget"]),
        2,
    )

    recent_pace_projected_end_balance = (
        round(
            remaining_budget
            - (recent_average * int(budget_data["remaining_days"])),
            2,
        )
        if recent_rows
        else None
    )

    if remaining_budget < 0 or risk_probability >= 0.75:
        status = "at_risk"
    elif (
        recent_rows
        and recent_average <= safe_daily_target
        and (
            cycle_pace_projected_end_balance < 0
            or risk_probability >= 0.50
        )
    ):
        status = "recovering"
    elif cycle_pace_projected_end_balance < 0 or risk_probability >= 0.50:
        status = "watch"
    else:
        status = "on_track"

    if status == "recovering":
        if cycle_pace_projected_end_balance < 0:
            cycle_context = (
                "Earlier cycle spending projected an EGP "
                f"{abs(cycle_pace_projected_end_balance):.2f} deficit."
            )
        else:
            cycle_context = (
                "The model still reports an overrun risk of "
                f"{risk_probability:.1%} from the whole-cycle history."
            )
        coaching_reasons = [
            cycle_context,
            (
                f"Your recent completed-day average is EGP {recent_average:.2f}, "
                f"which is EGP {daily_buffer:.2f} below the safe daily target of "
                f"EGP {safe_daily_target:.2f}."
            ),
        ]
        if recent_pace_projected_end_balance is not None:
            coaching_reasons.append(
                "Maintaining the recent pace could leave approximately EGP "
                f"{recent_pace_projected_end_balance:.2f} at cycle end."
            )
    elif status in {"watch", "at_risk"}:
        coaching_reasons = [
            (
                f"Your recent completed-day average is EGP {recent_average:.2f}, "
                f"compared with the safe daily target of EGP {safe_daily_target:.2f}."
            ),
            (
                "Reduce daily spending by approximately EGP "
                f"{daily_adjustment:.2f} to return to the safe pace."
            ),
        ]
    else:
        coaching_reasons = [
            (
                f"Your recent completed-day average is EGP {recent_average:.2f}, "
                f"which is within the safe daily target of EGP {safe_daily_target:.2f}."
            )
        ]

    def serialize_day(row: dict, day_state: str) -> dict:
        return {
            "date": str(row["date"]),
            "day_state": day_state,
            "allowed": round(float(row["available_today"]), 2),
            "daily_expenses": round(
                float(row["daily_expenses_today"]),
                2,
            ),
            "goal_contributions": round(
                float(row["goal_contributions_today"]),
                2,
            ),
            "used": round(float(row["used_today"]), 2),
            "remaining_for_day": round(
                float(row["remaining_today"]),
                2,
            ),
            "closing_cycle_balance": round(
                float(row["remaining_total_budget"]),
                2,
            ),
        }

    history = [
        serialize_day(row, "complete")
        for row in recent_rows
    ]
    today = (
        serialize_day(today_row, "in_progress")
        if today_row is not None
        else None
    )

    return {
        "mode": "shadow",
        "affects_financial_decisions": False,
        "cycle_id": budget_data["cycle_id"],
        "as_of_date": str(as_of_date),
        "status": status,
        "financial_position": {
            "available_budget": round(available_budget, 2),
            "remaining_budget": remaining_budget,
            "remaining_days": budget_data["remaining_days"],
            "safe_daily_target": safe_daily_target,
            "recent_completed_day_average": recent_average,
            "daily_adjustment_needed": daily_adjustment,
            "daily_buffer": daily_buffer,
            "cycle_pace_projected_end_balance": (
                cycle_pace_projected_end_balance
            ),
            "recent_pace_projected_end_balance": (
                recent_pace_projected_end_balance
            ),
        },
        "today": today,
        "recent_history": {
            "requested_completed_days": history_days,
            "returned_completed_days": len(history),
            "total_used": recent_total,
            "days_over_allowance": sum(
                1 for row in recent_rows
                if float(row["used_today"]) > float(row["available_today"])
            ),
            "days": history,
        },
        "risk": {
            "probability": risk_probability,
            "level": prediction["risk_level"],
            "confidence": prediction["confidence"],
            "reasons": coaching_reasons,
            "model_signals": prediction["reasons"],
            "model": prediction["model"],
        },
    }
