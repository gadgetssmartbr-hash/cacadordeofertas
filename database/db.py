"""
SQLite Database Layer for PriceGlitch & Drop Agent.
Handles product storage, historical price tracking, and alert cooldowns.
"""

import math
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from config.settings import settings


class PriceDatabase:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or settings.DB_PATH)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Table: products
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    marketplace TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    image_url TEXT,
                    category TEXT,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(marketplace, product_id)
                )
            """)

            # Table: price_history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    marketplace TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    price REAL NOT NULL,
                    original_price REAL,
                    discount_percent REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Index for fast historical lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_history_prod 
                ON price_history(marketplace, product_id, timestamp)
            """)

            # Table: alerts_sent (prevents duplicate spamming)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts_sent (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    marketplace TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    price_alerted REAL NOT NULL,
                    alert_type TEXT NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_prod 
                ON alerts_sent(marketplace, product_id, sent_at)
            """)

            conn.commit()

    def upsert_product(
        self,
        marketplace: str,
        product_id: str,
        title: str,
        url: str,
        image_url: Optional[str] = None,
        category: Optional[str] = None,
    ) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO products (marketplace, product_id, title, url, image_url, category, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(marketplace, product_id) DO UPDATE SET
                    title = excluded.title,
                    url = excluded.url,
                    image_url = coalesce(excluded.image_url, products.image_url),
                    category = coalesce(excluded.category, products.category),
                    last_updated = CURRENT_TIMESTAMP
            """, (marketplace, product_id, title, url, image_url, category))
            conn.commit()

    def record_price(
        self,
        marketplace: str,
        product_id: str,
        price: float,
        original_price: Optional[float] = None,
        discount_percent: Optional[float] = None,
    ) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO price_history (marketplace, product_id, price, original_price, discount_percent)
                VALUES (?, ?, ?, ?, ?)
            """, (marketplace, product_id, price, original_price, discount_percent))
            conn.commit()

    def get_historical_stats(self, marketplace: str, product_id: str) -> Dict[str, Any]:
        """
        Retrieves statistical aggregates: min, max, avg, sample count, and standard deviation.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT price FROM price_history
                WHERE marketplace = ? AND product_id = ?
                ORDER BY timestamp DESC
                LIMIT 60
            """, (marketplace, product_id))
            rows = cursor.fetchall()

            if not rows:
                return {
                    "count": 0,
                    "min_price": None,
                    "max_price": None,
                    "avg_price": None,
                    "std_dev": 0.0,
                    "prices": [],
                }

            prices = [row["price"] for row in rows]
            count = len(prices)
            avg_price = sum(prices) / count
            min_price = min(prices)
            max_price = max(prices)

            # Population standard deviation
            if count > 1:
                variance = sum((p - avg_price) ** 2 for p in prices) / (count - 1)
                std_dev = math.sqrt(variance)
            else:
                std_dev = 0.0

            return {
                "count": count,
                "min_price": min_price,
                "max_price": max_price,
                "avg_price": avg_price,
                "std_dev": std_dev,
                "prices": prices,
            }

    def should_alert(
        self,
        marketplace: str,
        product_id: str,
        current_price: float,
        cooldown_hours: Optional[int] = None,
    ) -> bool:
        """
        Checks if an alert for this product was already sent recently.
        Returns True if:
        1. No alert was ever sent.
        2. Last alert was sent more than `cooldown_hours` ago.
        3. Or current price is significantly lower (>= 10% lower) than the last alerted price.
        """
        hours = cooldown_hours if cooldown_hours is not None else settings.ALERT_COOLDOWN_HOURS
        since = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT price_alerted, sent_at
                FROM alerts_sent
                WHERE marketplace = ? AND product_id = ? AND sent_at >= ?
                ORDER BY sent_at DESC
                LIMIT 1
            """, (marketplace, product_id, since))
            row = cursor.fetchone()

            if not row:
                return True  # No alert in cooldown window

            last_price = row["price_alerted"]
            # If price dropped an additional 10% below what was already alerted, trigger again!
            if current_price < (last_price * 0.90):
                return True

            return False

    def record_alert(
        self,
        marketplace: str,
        product_id: str,
        price_alerted: float,
        alert_type: str,
    ) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO alerts_sent (marketplace, product_id, price_alerted, alert_type)
                VALUES (?, ?, ?, ?)
            """, (marketplace, product_id, price_alerted, alert_type))
            conn.commit()

    def get_recent_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.*, p.title, p.url, p.image_url, p.category
                FROM alerts_sent a
                LEFT JOIN products p ON a.marketplace = p.marketplace AND a.product_id = p.product_id
                ORDER BY a.sent_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_product(self, marketplace: str, product_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves product details along with its latest price reading."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.*, h.price as current_price, h.original_price, h.discount_percent, h.timestamp as price_timestamp
                FROM products p
                LEFT JOIN price_history h ON p.marketplace = h.marketplace AND p.product_id = h.product_id
                WHERE p.marketplace = ? AND p.product_id = ?
                ORDER BY h.timestamp DESC
                LIMIT 1
            """, (marketplace, product_id))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_product_price_timeline(self, marketplace: str, product_id: str) -> List[Dict[str, Any]]:
        """Retrieves chronological price history for Chart.js timeline graph."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT price, original_price, discount_percent, timestamp
                FROM price_history
                WHERE marketplace = ? AND product_id = ?
                ORDER BY timestamp ASC
            """, (marketplace, product_id))
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_deals(self, limit: int = 30, marketplace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves recent price drop alerts for the homepage feed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if marketplace and marketplace != "all":
                cursor.execute("""
                    SELECT a.id as alert_id, a.price_alerted, a.alert_type, a.sent_at,
                           p.product_id, p.marketplace, p.title, p.url, p.image_url, p.category,
                           h.original_price, h.discount_percent
                    FROM alerts_sent a
                    JOIN products p ON a.marketplace = p.marketplace AND a.product_id = p.product_id
                    LEFT JOIN price_history h ON a.marketplace = h.marketplace AND a.product_id = h.product_id AND a.price_alerted = h.price
                    WHERE a.marketplace = ?
                    GROUP BY a.marketplace, a.product_id
                    ORDER BY a.sent_at DESC
                    LIMIT ?
                """, (marketplace, limit))
            else:
                cursor.execute("""
                    SELECT a.id as alert_id, a.price_alerted, a.alert_type, a.sent_at,
                           p.product_id, p.marketplace, p.title, p.url, p.image_url, p.category,
                           h.original_price, h.discount_percent
                    FROM alerts_sent a
                    JOIN products p ON a.marketplace = p.marketplace AND a.product_id = p.product_id
                    LEFT JOIN price_history h ON a.marketplace = h.marketplace AND a.product_id = h.product_id AND a.price_alerted = h.price
                    GROUP BY a.marketplace, a.product_id
                    ORDER BY a.sent_at DESC
                    LIMIT ?
                """, (limit,))
            return [dict(row) for row in cursor.fetchall()]


# Global database instance
db = PriceDatabase()

