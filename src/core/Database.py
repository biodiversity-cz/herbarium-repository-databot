import json
import psycopg2
from core.ResultStatus import ResultStatus
from utils.types import Score
from config import config

def get_connection():

    return psycopg2.connect(
        dbname=config.get_database_config('database', 'jacq_dev'),
        user=config.get_database_config('user', 'databot'),
        password=config.get_database_config('password', 'databot'),
        host=config.get_database_config('host', 'localhost'),
        port=config.get_database_config('port', 5433)
    )

def register_databot(name: str, description: str, version: int, role: str) ->  int | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT databots.register_databot(%s, %s, %s, %s)", (name, description, version, role))
            return cur.fetchone()[0]

def fetch_records(databot_id: int, limit: int = 1000):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.id, databot_thumb_filename
                FROM photos p
                LEFT JOIN databots.databot_results dr
                    ON dr.photo_id = p.id
                    AND dr.databot_id = %s
                WHERE p.status_id > 1 --skip waiting, unprocessed
                    AND dr.id IS NULL
                ORDER BY p.id ASC
                LIMIT %s
                """,
                (databot_id,limit)
            )
            return cur.fetchall()

def save_success_result(databot_id: int, photo_id: int, result: Score ):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO databots.databot_results (databot_id, photo_id, result_data) VALUES (%s, %s, %s)",
                (databot_id, photo_id, json.dumps(result))
            )
        conn.commit()

def save_error_result(databot_id: int, photo_id: int, message: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO databots.databot_results (databot_id, photo_id, status, message) VALUES (%s, %s, %s, %s)",
                (databot_id, photo_id, ResultStatus.ERROR.value, message)
            )
        conn.commit()