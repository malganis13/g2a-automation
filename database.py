import sqlite3
import datetime
import json
import os
from datetime import timedelta
from g2a_config import DATABASE_FILE, PRICE_EXPIRY_DAYS


class PriceDatabase:
    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_FILE)
        self.conn.row_factory = sqlite3.Row  # Для доступа по ключам
        self.create_tables()

    def create_tables(self):
        """Создание всех необходимых таблиц"""
        
        # Таблица цен (старая)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                price REAL,
                region TEXT,
                date TIMESTAMP
            )
        """)

        # Таблица ID продуктов (старая)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS product_ids (
                id TEXT PRIMARY KEY,
                name TEXT,
                g2a_id TEXT,
                region TEXT DEFAULT 'GLOBAL',
                date TIMESTAMP
            )
        """)

        # ✅ НОВАЯ: Индивидуальные настройки товаров
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS product_settings (
                product_id TEXT PRIMARY KEY,
                game_name TEXT,
                min_floor_price REAL,
                undercut_amount REAL DEFAULT 0.01,
                auto_enabled INTEGER DEFAULT 0,
                updated_at TEXT
            )
        """)

        # ✅ НОВАЯ: Таблица заказов (для статистики продаж)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                product_id TEXT,
                product_name TEXT,
                price REAL,
                quantity INTEGER DEFAULT 1,
                customer_id TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # ✅ НОВАЯ: Таблица изменений цен (вместо JSON)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS price_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                game_name TEXT,
                old_price REAL,
                new_price REAL,
                market_price REAL,
                change_amount REAL,
                change_reason TEXT,
                created_at TEXT
            )
        """)

        # Добавляем колонку region если её нет
        try:
            self.conn.execute("ALTER TABLE product_ids ADD COLUMN region TEXT DEFAULT 'GLOBAL'")
            self.conn.commit()
        except:
            pass

        self.conn.commit()

    # ==================== PRODUCT SETTINGS ====================

    def get_product_settings(self, product_id):
        """
        ✅ НОВОЕ: Получить индивидуальные настройки товара
        
        Returns:
            dict или None
        """
        try:
            cursor = self.conn.execute("""
                SELECT * FROM product_settings WHERE product_id = ?
            """, (str(product_id),))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        except Exception as e:
            print(f"❌ Ошибка получения настроек: {e}")
            return None

    def set_product_settings(self, product_id, game_name=None, min_floor_price=None, 
                            undercut_amount=None, auto_enabled=None):
        """
        ✅ НОВОЕ: Установить индивидуальные настройки товара
        
        Args:
            product_id: ID товара
            game_name: Название игры
            min_floor_price: Минимальный порог цены
            undercut_amount: Снижение от конкурента (EUR)
            auto_enabled: Включено ли автоизменение (0/1)
        """
        try:
            now = datetime.datetime.now().isoformat()
            
            # Получаем текущие настройки
            current = self.get_product_settings(product_id)
            
            if current:
                # Обновляем существующие
                updates = []
                values = []
                
                if game_name is not None:
                    updates.append("game_name = ?")
                    values.append(game_name)
                if min_floor_price is not None:
                    updates.append("min_floor_price = ?")
                    values.append(min_floor_price)
                if undercut_amount is not None:
                    updates.append("undercut_amount = ?")
                    values.append(undercut_amount)
                if auto_enabled is not None:
                    updates.append("auto_enabled = ?")
                    values.append(auto_enabled)
                
                updates.append("updated_at = ?")
                values.append(now)
                values.append(str(product_id))
                
                query = f"UPDATE product_settings SET {', '.join(updates)} WHERE product_id = ?"
                self.conn.execute(query, values)
            else:
                # Создаём новую запись
                self.conn.execute("""
                    INSERT INTO product_settings 
                    (product_id, game_name, min_floor_price, undercut_amount, auto_enabled, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    str(product_id),
                    game_name,
                    min_floor_price if min_floor_price is not None else None,
                    undercut_amount if undercut_amount is not None else 0.01,
                    auto_enabled if auto_enabled is not None else 0,
                    now
                ))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения настроек: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_all_product_settings(self):
        """
        ✅ НОВОЕ: Получить настройки всех товаров
        
        Returns:
            dict: {product_id: settings_dict}
        """
        try:
            cursor = self.conn.execute("SELECT * FROM product_settings")
            rows = cursor.fetchall()
            
            result = {}
            for row in rows:
                data = dict(row)
                result[data['product_id']] = data
            
            return result
        except Exception as e:
            print(f"❌ Ошибка получения всех настроек: {e}")
            return {}

    def delete_product_settings(self, product_id):
        """Удалить настройки товара"""
        try:
            self.conn.execute("DELETE FROM product_settings WHERE product_id = ?", (str(product_id),))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Ошибка удаления настроек: {e}")
            return False

    # ==================== PRICE CHANGES ====================

    def save_price_change(self, product_id, old_price, new_price, market_price, reason="manual", game_name=""):
        """
        ✅ ОБНОВЛЕНО: Сохранить изменение цены в БД (вместо JSON)
        """
        try:
            now = datetime.datetime.now().isoformat()
            change_amount = round(new_price - old_price, 2)
            
            self.conn.execute("""
                INSERT INTO price_changes 
                (product_id, game_name, old_price, new_price, market_price, change_amount, change_reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(product_id),
                game_name,
                old_price,
                new_price,
                market_price,
                change_amount,
                reason,
                now
            ))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения изменения: {e}")
            return False

    def get_price_changes_stats(self, days=1):
        """
        ✅ НОВОЕ: Получить статистику изменений за период
        
        Args:
            days: Количество дней (1, 7, 30)
        
        Returns:
            dict с детальной статистикой
        """
        try:
            cutoff_date = (datetime.datetime.now() - timedelta(days=days)).isoformat()
            
            # Общая статистика
            cursor = self.conn.execute("""
                SELECT 
                    COUNT(*) as total_changes,
                    SUM(CASE WHEN change_amount < 0 THEN 1 ELSE 0 END) as price_decreases,
                    SUM(CASE WHEN change_amount > 0 THEN 1 ELSE 0 END) as price_increases,
                    AVG(change_amount) as avg_price_change,
                    SUM(change_amount) as total_price_change,
                    COUNT(CASE WHEN DATE(created_at) = DATE('now') THEN 1 END) as today_changes
                FROM price_changes
                WHERE created_at >= ?
            """, (cutoff_date,))
            
            summary = dict(cursor.fetchone())
            
            # Топ изменённых игр
            cursor = self.conn.execute("""
                SELECT 
                    game_name,
                    product_id,
                    COUNT(*) as change_count,
                    MIN(old_price) as min_old_price,
                    MAX(new_price) as max_new_price,
                    AVG(change_amount) as avg_change
                FROM price_changes
                WHERE created_at >= ?
                GROUP BY product_id
                ORDER BY change_count DESC
                LIMIT 20
            """, (cutoff_date,))
            
            top_changed_games = [dict(row) for row in cursor.fetchall()]
            
            # Последние изменения
            cursor = self.conn.execute("""
                SELECT *
                FROM price_changes
                WHERE created_at >= ?
                ORDER BY created_at DESC
                LIMIT 100
            """, (cutoff_date,))
            
            recent_changes = [dict(row) for row in cursor.fetchall()]
            
            # Определяем период
            period_map = {1: "За сегодня", 7: "За 7 дней", 30: "За 30 дней"}
            
            return {
                "period": period_map.get(days, f"За {days} дней"),
                "summary": {
                    "total_changes": summary["total_changes"] or 0,
                    "price_decreases": summary["price_decreases"] or 0,
                    "price_increases": summary["price_increases"] or 0,
                    "avg_price_change": round(summary["avg_price_change"] or 0, 2),
                    "total_price_change": round(summary["total_price_change"] or 0, 2),
                    "today_changes": summary["today_changes"] or 0
                },
                "top_changed_games": top_changed_games,
                "recent_changes": recent_changes
            }
        except Exception as e:
            print(f"❌ Ошибка получения статистики: {e}")
            import traceback
            traceback.print_exc()
            return {
                "period": f"За {days} дней",
                "summary": {
                    "total_changes": 0,
                    "price_decreases": 0,
                    "price_increases": 0,
                    "avg_price_change": 0,
                    "total_price_change": 0,
                    "today_changes": 0
                },
                "top_changed_games": [],
                "recent_changes": []
            }

    # ==================== ORDERS (продажи) ====================

    def save_order(self, order_id, product_id, product_name, price, quantity=1, 
                   customer_id="", status="completed"):
        """
        ✅ НОВОЕ: Сохранить заказ (продажу)
        """
        try:
            now = datetime.datetime.now().isoformat()
            
            self.conn.execute("""
                INSERT OR REPLACE INTO orders 
                (order_id, product_id, product_name, price, quantity, customer_id, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(order_id),
                str(product_id),
                product_name,
                price,
                quantity,
                customer_id,
                status,
                now,
                now
            ))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения заказа: {e}")
            return False

    def get_sales_stats(self, days=1):
        """
        ✅ НОВОЕ: Получить статистику продаж за период
        
        Returns:
            dict с детальной статистикой продаж
        """
        try:
            cutoff_date = (datetime.datetime.now() - timedelta(days=days)).isoformat()
            
            # Общая статистика
            cursor = self.conn.execute("""
                SELECT 
                    COUNT(*) as total_sales,
                    SUM(price * quantity) as total_revenue,
                    AVG(price) as avg_price,
                    SUM(quantity) as total_items_sold
                FROM orders
                WHERE created_at >= ?
            """, (cutoff_date,))
            
            summary = dict(cursor.fetchone())
            
            # Топ проданных игр
            cursor = self.conn.execute("""
                SELECT 
                    product_name,
                    product_id,
                    COUNT(*) as sales_count,
                    SUM(quantity) as items_sold,
                    SUM(price * quantity) as revenue,
                    AVG(price) as avg_price
                FROM orders
                WHERE created_at >= ?
                GROUP BY product_id
                ORDER BY sales_count DESC
                LIMIT 20
            """, (cutoff_date,))
            
            top_products = [dict(row) for row in cursor.fetchall()]
            
            # Последние заказы
            cursor = self.conn.execute("""
                SELECT *
                FROM orders
                WHERE created_at >= ?
                ORDER BY created_at DESC
                LIMIT 50
            """, (cutoff_date,))
            
            recent_orders = [dict(row) for row in cursor.fetchall()]
            
            period_map = {1: "За сегодня", 7: "За 7 дней", 30: "За 30 дней"}
            
            return {
                "period": period_map.get(days, f"За {days} дней"),
                "summary": {
                    "total_sales": summary["total_sales"] or 0,
                    "total_revenue": round(summary["total_revenue"] or 0, 2),
                    "avg_price": round(summary["avg_price"] or 0, 2),
                    "total_items_sold": summary["total_items_sold"] or 0
                },
                "top_products": top_products,
                "recent_orders": recent_orders
            }
        except Exception as e:
            print(f"❌ Ошибка получения статистики продаж: {e}")
            return {
                "period": f"За {days} дней",
                "summary": {
                    "total_sales": 0,
                    "total_revenue": 0,
                    "avg_price": 0,
                    "total_items_sold": 0
                },
                "top_products": [],
                "recent_orders": []
            }

    # ==================== СТАРЫЕ МЕТОДЫ (совместимость) ====================

    def get_price(self, name, region="GLOBAL"):
        """Получить цену из кэша"""
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
        """Сохранить цену в кэш"""
        now = datetime.datetime.now().isoformat()

        self.conn.execute("""
            INSERT OR REPLACE INTO prices (name, price, region, date)
            VALUES (?, ?, ?, ?)
        """, (name, price, region, now))
        self.conn.commit()

    def get_g2a_id(self, name, region="GLOBAL"):
        """Получить G2A ID из кэша"""
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
        """Сохранить G2A ID в кэш"""
        now = datetime.datetime.now().isoformat()
        unique_id = f"{name}_{region}"

        self.conn.execute("""
            INSERT OR REPLACE INTO product_ids (id, name, g2a_id, region, date)
            VALUES (?, ?, ?, ?, ?)
        """, (unique_id, name, g2a_id, region, now))
        self.conn.commit()

    def close(self):
        """Закрыть соединение"""
        self.conn.close()