import psycopg2
import os

def get_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "jacq_test"),
        user=os.getenv("DB_USER", "jacq"),
        password=os.getenv("DB_PASS", "jacq"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5433"),
    )

def register_databot(name: str, description: str, version: int, role: str) ->  int | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT register_databot(%s, %s, %s, %s)", (name, description, version, role))
            return cur.fetchone()[0]
