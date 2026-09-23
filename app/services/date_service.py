import os
from datetime import datetime
from zoneinfo import ZoneInfo


def current_business_date():
    timezone_name = os.getenv("APP_TIMEZONE", "Africa/Cairo")
    return datetime.now(ZoneInfo(timezone_name)).date()
