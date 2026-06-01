"""
POS transaction data loader.
Reads the CSV file and loads it into the PostgreSQL database.
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.database import db

logger = logging.getLogger(__name__)

# Path to POS CSV (relative to project root)
POS_CSV_PATH = (
    Path(__file__).parent.parent
    / "Project details"
    / "Brigade_Bangalore_10_April_26 (1)bc6219c.csv"
)


async def load_pos_data(csv_path: Path | None = None) -> int:
    """
    Load POS transaction data from CSV into the database.

    Returns the number of rows inserted.
    """
    path = csv_path or POS_CSV_PATH

    if not path.exists():
        logger.warning(f"POS CSV not found at {path}")
        return 0

    rows_inserted = 0

    try:
        async with db.acquire() as conn:
            # Check if data already loaded
            existing = await conn.fetchval("SELECT COUNT(*) FROM pos_transactions")
            if existing > 0:
                logger.info(f"POS data already loaded ({existing} rows)")
                return existing

            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    try:
                        # Parse date and time into a single timestamp
                        order_date = row.get("order_date", "").strip()
                        order_time = row.get("order_time", "").strip()

                        timestamp = None
                        if order_date and order_time:
                            # Date format: DD-MM-YYYY, Time: HH:MM:SS
                            dt_str = f"{order_date} {order_time}"
                            try:
                                dt = datetime.strptime(dt_str, "%d-%m-%Y %H:%M:%S")
                                timestamp = dt.replace(tzinfo=timezone.utc)
                            except ValueError:
                                pass

                        await conn.execute(
                            """
                            INSERT INTO pos_transactions (
                                order_id, invoice_number, store_id,
                                order_date, order_time, timestamp,
                                customer_name, sku, product_name,
                                brand_name, department, sub_category,
                                qty, gmv, nmv, total_amount,
                                salesperson_id, salesperson_name
                            ) VALUES (
                                $1, $2, $3, $4, $5, $6, $7, $8, $9,
                                $10, $11, $12, $13, $14, $15, $16, $17, $18
                            )
                            """,
                            row.get("order_id", "").strip(),
                            row.get("invoice_number", "").strip(),
                            row.get("store_id", "").strip(),
                            (
                                datetime.strptime(order_date, "%d-%m-%Y").date()
                                if order_date
                                else None
                            ),
                            (
                                datetime.strptime(order_time, "%H:%M:%S").time()
                                if order_time
                                else None
                            ),
                            timestamp,
                            row.get("customer_name", "").strip(),
                            row.get("sku", "").strip(),
                            row.get("product_name", "").strip(),
                            row.get("brand_name", "").strip(),
                            row.get("dep_name", "").strip(),
                            row.get("sub_category", "").strip(),
                            int(row.get("qty", "1").strip() or "1"),
                            float(row.get("GMV", "0").strip() or "0"),
                            float(row.get("NMV", "0").strip() or "0"),
                            float(row.get("total_amount", "0").strip() or "0"),
                            row.get("salesperson_id", "").strip(),
                            row.get("salesperson_name", "").strip(),
                        )
                        rows_inserted += 1

                    except Exception as e:
                        logger.warning(f"Failed to insert POS row: {e}")
                        continue

        logger.info(f"Loaded {rows_inserted} POS transactions from {path}")

    except Exception as e:
        logger.error(f"Failed to load POS data: {e}")

    return rows_inserted
