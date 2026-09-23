import time

# Legacy metric names remain during the Bako transition so existing dashboards
# keep their historical time series. A later migration can dual-publish names.

from fastapi import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest
)


HTTP_REQUESTS_TOTAL = Counter(
    "masarefy_http_requests_total",
    "Total HTTP requests received by the Bako API.",
    ["method", "endpoint", "status_code"]
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "masarefy_http_request_duration_seconds",
    "HTTP request duration in seconds for the Bako API.",
    ["method", "endpoint", "status_code"]
)

EXPENSES_CREATED_TOTAL = Counter(
    "masarefy_expenses_created_total",
    "Total daily expenses created successfully.",
    ["payment_channel", "category"]
)

EXPENSE_AMOUNT_TOTAL = Counter(
    "masarefy_expense_amount_total",
    "Total daily expense amount created successfully.",
    ["payment_channel", "category"]
)

BUDGET_CALCULATIONS_TOTAL = Counter(
    "masarefy_budget_calculations_total",
    "Total budget calculations completed successfully."
)

LOGIN_SUCCESS_TOTAL = Counter(
    "masarefy_login_success_total",
    "Total successful login attempts."
)

LOGIN_FAILURE_TOTAL = Counter(
    "masarefy_login_failure_total",
    "Total failed login attempts."
)

GOAL_CONTRIBUTIONS_TOTAL = Counter(
    "masarefy_goal_contributions_total",
    "Total goal contributions created successfully."
)

GOAL_CONTRIBUTION_AMOUNT_TOTAL = Counter(
    "masarefy_goal_contribution_amount_total",
    "Total goal contribution amount created successfully."
)

AI_INSIGHTS_GENERATED_TOTAL = Counter(
    "masarefy_ai_insights_generated_total",
    "Total AI coach insights generated successfully.",
    ["insight_type"]
)


def record_expense_created(payment_channel, category, amount):
    EXPENSES_CREATED_TOTAL.labels(
        payment_channel or "unknown",
        category or "unknown"
    ).inc()
    EXPENSE_AMOUNT_TOTAL.labels(
        payment_channel or "unknown",
        category or "unknown"
    ).inc(float(amount or 0))


def record_goal_contribution(amount):
    GOAL_CONTRIBUTIONS_TOTAL.inc()
    GOAL_CONTRIBUTION_AMOUNT_TOTAL.inc(float(amount or 0))


def record_ai_insights_generated(insights):
    for insight in insights or []:
        insight_type = insight.get("type") or "unknown"
        AI_INSIGHTS_GENERATED_TOTAL.labels(insight_type).inc()


def get_route_template(request):
    route = request.scope.get("route")

    if route and getattr(route, "path", None):
        return route.path

    return request.url.path


def metrics_response():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


def setup_metrics(app):
    @app.middleware("http")
    async def prometheus_metrics_middleware(request, call_next):
        start_time = time.perf_counter()
        status_code = "500"
        endpoint = request.url.path

        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            endpoint = get_route_template(request)

            return response
        finally:
            duration = time.perf_counter() - start_time

            HTTP_REQUESTS_TOTAL.labels(
                request.method,
                endpoint,
                status_code
            ).inc()

            HTTP_REQUEST_DURATION_SECONDS.labels(
                request.method,
                endpoint,
                status_code
            ).observe(duration)

    app.add_api_route(
        "/metrics",
        metrics_response,
        methods=["GET"],
        include_in_schema=False
    )
