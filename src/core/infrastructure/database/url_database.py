from src.core.infrastructure.database.base_database import BaseDatabase


class UrlDatabase(BaseDatabase):
    def fetch_url_records(self, databot_id: int, limit: int = 1000):
        """
        Fetch records for URL-based databots.
        This method retrieves records that don't have results yet for this databot.
        """
        return self.fetchall(
            """
            SELECT p.id, p.uuid, p.scientific_name, p.family, p.institution_code, p.collection_code
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