import psycopg2

from config import config

def get_connection():

    return psycopg2.connect(
        dbname=config.get_database_config('database'),
        user=config.get_database_config('user'),
        password=config.get_database_config('password'),
        host=config.get_database_config('host'),
        port=config.get_database_config('port')
    )

def register_databot(name: str, description: str, version: int, role: str) ->  int | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT register_databot(%s, %s, %s, %s)", (name, description, version, role))
            return cur.fetchone()[0]
