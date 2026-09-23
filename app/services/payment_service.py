def build_daily_spending_by_date(spending_rows):
    spending_by_date = {}

    for expense_date, amount, _payment_channel in spending_rows:
        spending_by_date[expense_date] = round(
            spending_by_date.get(expense_date, 0) + float(amount),
            2
        )

    return spending_by_date


def build_goal_contributions_by_date(contribution_rows):
    contributions_by_date = {}

    for contribution_date, amount in contribution_rows:
        contributions_by_date[contribution_date] = round(
            contributions_by_date.get(contribution_date, 0) + float(amount),
            2
        )

    return contributions_by_date


def add_goal_contributions(spending_by_date, contribution_rows):
    combined = dict(spending_by_date)

    for contribution_date, amount in contribution_rows:
        combined[contribution_date] = round(
            combined.get(contribution_date, 0) + float(amount),
            2
        )

    return combined
