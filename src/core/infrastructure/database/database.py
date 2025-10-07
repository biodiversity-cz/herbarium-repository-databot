from src.core.infrastructure.database.base_database import BaseDatabase


class Database(BaseDatabase):
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