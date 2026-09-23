import os

import psycopg2


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "postgres"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        database=os.getenv("POSTGRES_DB", "finance"),
        user=os.getenv("POSTGRES_USER", "user"),
        password=os.getenv("POSTGRES_PASSWORD", "pass")
    )
