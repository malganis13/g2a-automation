import sqlite3
import datetime
from g2a_config import DATABASE_FILE, PRICE_EXPIRY_DAYS


class PriceDatabase:
    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_FILE)
        self.create_tables()

    def create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                price REAL,
                region TEXT,
                date TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS product_ids (
                id TEXT PRIMARY KEY,
                name TEXT,
                g2a_id TEXT,
                region TEXT DEFAULT 'GLOBAL',
                date TIMESTAMP
            )
        """)

        try:
            self.conn.execute("ALTER TABLE product_ids ADD COLUMN region TEXT DEFAULT 'GLOBAL'")
            self.conn.commit()
        except:
            pass

        self.conn.commit()

    def get_price(self, name, region="GLOBAL"):
        cursor = self.conn.execute("""
            SELECT price, date FROM prices 
            WHERE name = ? AND region = ?
        """, (name, region))

        result = cursor.fetchone()
        if not result:
            return None

        price, date_str = result
        stored_date = datetime.datetime.fromisoformat(date_str)
        now = datetime.datetime.now()

        if (now - stored_date).days < PRICE_EXPIRY_DAYS:
            return price
        else:
            return None

    def save_price(self, name, price, region="GLOBAL"):
        now = datetime.datetime.now().isoformat()

        self.conn.execute("""
            INSERT OR REPLACE INTO prices (name, price, region, date)
            VALUES (?, ?, ?, ?)
        """, (name, price, region, now))
        self.conn.commit()

    def get_g2a_id(self, name, region="GLOBAL"):
        cursor = self.conn.execute("""
            SELECT g2a_id, date FROM product_ids 
            WHERE name = ? AND region = ?
        """, (name, region))

        result = cursor.fetchone()
        if not result:
            return None

        g2a_id, date_str = result
        stored_date = datetime.datetime.fromisoformat(date_str)
        now = datetime.datetime.now()

        if (now - stored_date).days < PRICE_EXPIRY_DAYS:
            return g2a_id
        else:
            return None

    def save_g2a_id(self, name, g2a_id, region="GLOBAL"):
        now = datetime.datetime.now().isoformat()

        unique_id = f"{name}_{region}"

        self.conn.execute("""
            INSERT OR REPLACE INTO product_ids (id, name, g2a_id, region, date)
            VALUES (?, ?, ?, ?, ?)
        """, (unique_id, name, g2a_id, region, now))
        self.conn.commit()

    def close(self):
        self.conn.close()