import json
import psycopg2
import math
import psycopg2.extras
from core.ResultStatus import ResultStatus
from utils.types import Score
from config import config


class BaseDatabase:
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
        self.conn.commit()
        return result["register_databot"] if result else None  # název sloupce podle DB funkce

    def save_success_result(self, databot_id: int, photo_id: int, result: Score):
        """
        Save successful result for databot.
        """
        safe_result = self.sanitize(result)
        json_data = json.dumps(safe_result)
        self.execute(
            "INSERT INTO databots.databot_results (databot_id, photo_id, result_data) VALUES (%s, %s, %s)",
            (databot_id, photo_id, json_data)
        )

    def save_error_result(self, databot_id: int, photo_id: int, message: str):
        """
        Save error result for databot.
        """
        self.execute(
            "INSERT INTO databots.databot_results (databot_id, photo_id, status, message) VALUES (%s, %s, %s, %s)",
            (databot_id, photo_id, ResultStatus.ERROR.value, message)
        )

    def sanitize(self, obj):
        """
        Sanitize object for JSON serialization.
        """
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        elif isinstance(obj, dict):
            return {k: self.sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self.sanitize(x) for x in obj]
        return obj