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
                 JOIN photos_status s ON (s.id = p.status_id)
            WHERE s.succession > 1 -- skip waiting/unprocessed
              AND dr.id IS NULL
            ORDER BY p.id ASC
                LIMIT %s
            """,
            (databot_id, limit)
        )

    def records_with_specimen(self, databot_id: int, limit: int = 1000):
        """
        Fetch records for URL-based databots.
        """
        return self.fetchall(
            """
            SELECT p.id, p.specimen_pid
            FROM photos p
                     LEFT JOIN databots.databot_results dr
                               ON dr.photo_id = p.id
                                   AND dr.databot_id = %s
                     JOIN photos_status s ON (s.id = p.status_id)
            WHERE s.succession >= 4 -- having specimen              
                    AND (dr.id IS NULL)-- OR dr.created_at < now() - interval '3 months')
            ORDER BY p.id ASC
                LIMIT %s
            """,
            (databot_id, limit)
        )