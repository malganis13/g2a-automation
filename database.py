import sqlite3
import datetime
from g2a_config import DATABASE_FILE, PRICE_EXPIRY_DAYS


class PriceDatabase:
    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_FILE)
        self.create_tables()

    def save_price_change(self, product_id, old_price, new_price, market_price, reason="manual"):
        """
        ✅ НОВАЯ ФУНКЦИЯ: Сохранить изменение цены в базу
        """
        try:
            stats_file = "price_changes_stats.json"

            if os.path.exists(stats_file):
                with open(stats_file, 'r', encoding='utf-8') as f:
                    stats = json.load(f)
            else:
                stats = []

            stats.append({
                "timestamp": datetime.now().isoformat(),
                "product_id": product_id,
                "old_price": old_price,
                "new_price": new_price,
                "market_price": market_price,
                "change": round(new_price - old_price, 2),
                "reason": reason
            })

            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=4, ensure_ascii=False)

            return True

        except Exception as e:
            print(f"❌ Ошибка сохранения статистики: {e}")
            return False

    def get_stats_for_period(self, days=1):
        """
        ✅ НОВАЯ ФУНКЦИЯ: Получить статистику за период
        """
        try:
            stats_file = "price_changes_stats.json"

            if not os.path.exists(stats_file):
                return {
                    "total_changes": 0,
                    "price_increases": 0,
                    "price_decreases": 0,
                    "avg_change": 0,
                    "total_change": 0
                }

            with open(stats_file, 'r', encoding='utf-8') as f:
                all_stats = json.load(f)

            # Фильтруем по дате
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_stats = [
                s for s in all_stats
                if datetime.fromisoformat(s.get("timestamp", "")) > cutoff_date
            ]

            if not recent_stats:
                return {
                    "total_changes": 0,
                    "price_increases": 0,
                    "price_decreases": 0,
                    "avg_change": 0,
                    "total_change": 0
                }

            increases = sum(1 for s in recent_stats if s["change"] > 0)
            decreases = sum(1 for s in recent_stats if s["change"] < 0)
            total_change = sum(s["change"] for s in recent_stats)
            avg_change = total_change / len(recent_stats) if recent_stats else 0

            return {
                "total_changes": len(recent_stats),
                "price_increases": increases,
                "price_decreases": decreases,
                "avg_change": round(avg_change, 2),
                "total_change": round(total_change, 2)
            }

        except Exception as e:
            print(f"❌ Ошибка получения статистики: {e}")
            return {
                "total_changes": 0,
                "price_increases": 0,
                "price_decreases": 0,
                "avg_change": 0,
                "total_change": 0
            }

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