from core.infrastructure.database.base_database import BaseDatabase


class Database(BaseDatabase):
    def fetch_records(self, databot_id: int, limit: int = 1000):
        return self.fetchall(
            """
            SELECT p.id, bucket_suffix, databot_thumb_filename
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

    # use for Hespi&comp
    def fetch_specimen_type_records(self, databot_id: int, limit: int = 1000):
        return self.fetchall(
            """
            SELECT p.id, bucket_suffix, databot_thumb_filename
            FROM photos p
                     LEFT JOIN databots.databot_results dr
                               ON dr.photo_id = p.id
                                   AND dr.databot_id = %s
            WHERE p.status_id > 1 -- skip waiting/unprocessed
              AND p.type_id = 1   -- only "Specimen" type of photos
              AND dr.id IS NULL
            ORDER BY p.id ASC
                LIMIT %s
            """,
            (databot_id, limit)
        )