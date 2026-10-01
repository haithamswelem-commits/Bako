from fastapi import APIRouter, Depends

from app.services.ai_insights_service import (
    generate_ai_insights
)

from app.dependencies import get_current_user
from app.services.analysis_service import (
    calculate_spending_analysis
)


router = APIRouter()


@router.get("/spending-analysis")
def spending_analysis(
    cycle_id: int,
    current_user=Depends(get_current_user)
):
    user_id = current_user["id"]

    data, error = calculate_spending_analysis(
        cycle_id=cycle_id,
        user_id=user_id
    )

    if error:
        return {
            "error": error
        }

    return data

@router.get("/ai-insights")
def ai_insights(
    cycle_id: int,
    current_user=Depends(get_current_user)
):
    user_id = current_user["id"]

    data, error = generate_ai_insights(
        cycle_id=cycle_id,
        user_id=user_id
    )

    if error:
        return {
            "error": error
        }

    return data