import json
import psycopg2
import psycopg2.extras
from core.ResultStatus import ResultStatus
from utils.types import Score
from config import config

class Database:
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=config.get_database_config('database', 'jacq_dev'),
            user=config.get_database_config('user', 'databot'),
            password=config.get_database_config('password', 'databot'),
            host=config.get_database_config('host', 'localhost'),
            port=config.get_database_config('port', 5433)
        )

    def cursor(self):
        return self.conn.cursor()

    def fetchone(self, query: str, params=()):
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            return cur.fetchone()

    def fetchall(self, query: str, params=()):
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def execute(self, query: str, params: dict | tuple = (), commit: bool = True):
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            try:
                result = cur.fetchall()  # pokud je SELECT/RETURNING
            except psycopg2.ProgrammingError:
                result = None  # pokud není žádný výsledek
        if commit:
            self.conn.commit()
        return result

    def close(self):
        self.conn.close()


    def register_databot(self, name: str, description: str, version: int, role: str) -> int | None:
        result = self.fetchone(
            "SELECT databots.register_databot(%s, %s, %s, %s)",
            (name, description, version, role)
        )
        return result["register_databot"] if result else None  # název sloupce podle DB funkce


    def fetch_records(self, databot_id: int, limit: int = 1000):
        return self.fetchall(
            """
            SELECT p.id, databot_thumb_filename
            FROM photos p
                     LEFT JOIN databots.databot_results dr
                               ON dr.photo_id = p.id
                                   AND dr.databot_id = %s
            WHERE p.status_id > 1 -- skip waiting/unprocessed
              AND dr.id IS NULL
            ORDER BY p.id ASC
                LIMIT %s
            """,
            (databot_id, limit)
        )
        # teď vrací list dictů: row["id"], row["databot_thumb_filename"]


    def save_success_result(self, databot_id: int, photo_id: int, result: Score):
        self.execute(
            "INSERT INTO databots.databot_results (databot_id, photo_id, result_data) VALUES (%s, %s, %s)",
            (databot_id, photo_id, json.dumps(result))
        )


    def save_error_result(self, databot_id: int, photo_id: int, message: str):
        self.execute(
            "INSERT INTO databots.databot_results (databot_id, photo_id, status, message) VALUES (%s, %s, %s, %s)",
            (databot_id, photo_id, ResultStatus.ERROR.value, message)
        )
