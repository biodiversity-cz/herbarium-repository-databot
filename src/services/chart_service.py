import io
import matplotlib
matplotlib.use("Agg")  # toto musí být *před* importem pyplot
import matplotlib.pyplot as plt
from src.core.infrastructure.database.database import Database

class ChartService:
    def __init__(self, db: Database | None = None):
        """
        Pokud není předaná instance Database, vytvoří se nová.
        """
        self.db = db or Database()

    def generate_histogram(self, metric: str, highlight: float, bins: int = 50) -> io.BytesIO | None:
        """
        Vygeneruje histogram pro danou metriku s dynamickým min/max v DB.
        SELECT dotazy jsou read-only, commit se nepoužívá.
        """
        # 1) zjistit min a max
        min_max_query = """
                        SELECT MIN((elem ->>'value')::float) AS min_val,
                               MAX((elem ->>'value')::float) AS max_val
                        FROM databots.databot_results,
                             LATERAL jsonb_array_elements(result_data) AS elem
                        WHERE elem->>'name' = %s \
                        """
        result = self.db.fetchone(min_max_query, (metric,))
        if not result or result["min_val"] is None or result["max_val"] is None:
            return None

        min_val = result["min_val"]
        max_val = result["max_val"]

        # 2) histogram s width_bucket
        histogram_query = """
                          SELECT width_bucket((elem ->>'value'):: float, %s, %s, %s) AS bucket,
                                 COUNT(*) AS count
                          FROM databots.databot_results, LATERAL jsonb_array_elements(result_data) AS elem
                          WHERE elem->>'name' = %s
                          GROUP BY bucket
                          ORDER BY bucket \
                          """
        rows = self.db.fetchall(histogram_query, (min_val, max_val, bins, metric))
        if not rows:
            return None

        counts = [row["count"] for row in rows]
        bin_centers = [min_val + (row["bucket"] - 0.5) * (max_val - min_val) / bins for row in rows]

        # 3) vykreslení grafu
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(bin_centers, counts, width=(max_val - min_val) / bins * 0.9, edgecolor="black")
        ax.axvline(highlight, color="red", linestyle="--", linewidth=2, label=f"Highlight: {highlight}")
        ax.set_xlabel(metric)
        ax.set_ylabel("Count")
        ax.set_title(f"Distribution of {metric}")
        ax.legend()

        # 4) export do PNG
        buf = io.BytesIO()
        plt.tight_layout()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return buf

    def generate_boxplot(self, metric: str, highlight: float) -> io.BytesIO | None:
        """
        Vytvoří boxplot dané metriky, highlight hodnotu vykreslí červenou linkou.
        Kvantily jsou vypočteny přímo v PostgreSQL.
        """
        query = """
                SELECT percentile_cont(0.25) WITHIN GROUP (ORDER BY (elem->>'value')::float) AS q1,
                percentile_cont(0.5)  WITHIN \
                GROUP (ORDER BY (elem->>'value'):: float) AS median,
                    percentile_cont(0.75) WITHIN \
                GROUP (ORDER BY (elem->>'value'):: float) AS q3,
                    MIN ((elem->>'value'):: float) AS min_val,
                    MAX ((elem->>'value'):: float) AS max_val
                FROM databots.databot_results, LATERAL jsonb_array_elements(result_data) AS elem
                WHERE elem->>'name' = %s \
                """
        result = self.db.fetchone(query, (metric,))
        if not result or result["q1"] is None:
            return None  # žádná data

        # extrakce kvantilů
        q1 = result["q1"]
        median = result["median"]
        q3 = result["q3"]
        min_val = result["min_val"]
        max_val = result["max_val"]

        # boxplot data pro matplotlib
        box_data = [min_val, q1, median, q3, max_val]

        # vykreslení boxplotu
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bxp([{
            'med': median,
            'q1': q1,
            'q3': q3,
            'whislo': min_val,
            'whishi': max_val,
            'fliers': []
        }], vert=True, patch_artist=True)

        # červená linka pro highlight
        ax.axhline(highlight, color="red", linestyle="--", linewidth=2, label=f"Highlight: {highlight}")

        ax.set_xlabel(metric)
        ax.set_ylabel("Value")
        ax.set_title(f"Boxplot of {metric}")
        ax.legend()

        # export do PNG
        buf = io.BytesIO()
        plt.tight_layout()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return buf