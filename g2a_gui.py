import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import asyncio
import threading
import json
import os
from datetime import datetime
from pathlib import Path
import httpx
import requests
import traceback  # ✅ ДОБАВЛЕНО

# Импорты модулей
from key_manager import KeyManager, G2AOfferCreator
from price_parser import KeyPriceParser
from database import PriceDatabase
from g2a_api_client import G2AApiClient
import g2a_config

# Настройка темы
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class G2AAutomationGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("G2A Automation Tool")
        self.geometry("1400x800")

        # Инициализация компонентов
        self.key_manager = KeyManager()
        self.price_parser = KeyPriceParser()
        self.db = PriceDatabase()
        self.api_client = None

        # Переменные настроек
        self.telegram_enabled = tk.BooleanVar(value=False)
        self.seller_id_var = tk.StringVar(value="")

        # Для хранения данных офферов
        self.offers_data = {}
        
        # ✅ НОВОЕ: Храним цены конкурентов
        self.competitor_prices = {}
        
        # ✅ НОВОЕ: Выбранные офферы (чекбоксы)
        self.selected_offers = set()

        # Авто-процесс
        self.auto_process = None
        self.auto_running = False
        self.auto_changer = None

        # Переменная для поиска
        self.search_var = tk.StringVar()

        self.create_widgets()
        self.load_all_configs()

    def create_widgets(self):
        # Табы
        self.tabview = ctk.CTkTabview(self, width=1350, height=750)
        self.tabview.pack(padx=10, pady=10, fill="both", expand=True)

        # Создание вкладок
        self.tab_settings = self.tabview.add("⚙️ Настройки")
        self.tab_auto = self.tabview.add("🤖 Автоизменение + Офферы")  # ✅ ОБЪЕДИНЕНО!
        self.tab_parsing = self.tabview.add("📊 Парсинг")
        self.tab_keys = self.tabview.add("🔑 Ключи")
        self.tab_stats = self.tabview.add("📈 Статистика")

        self.setup_settings_tab()
        self.setup_auto_offers_tab()  # ✅ НОВАЯ ФУНКЦИЯ!
        self.setup_parsing_tab()
        self.setup_keys_tab()
        self.setup_stats_tab()

    def load_offers(self):
        """✅ ИСПРАВЛЕНО: Загрузка офферов с полным выводом ошибок"""
        def run():
            loop = None
            try:
                print("🔄 Начинаем загрузку офферов...")
                
                # Проверяем настройки
                if not g2a_config.G2A_CLIENT_ID or not g2a_config.G2A_CLIENT_SECRET:
                    error_msg = "❌ G2A API не настроен! Проверьте настройки."
                    print(error_msg)
                    messagebox.showerror("Ошибка", error_msg)
                    return
                
                print(f"✅ Client ID: {g2a_config.G2A_CLIENT_ID[:10]}...")
                print(f"✅ Client Secret: {'*' * 20}")
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                print("🔑 Создаем API клиент...")
                self.api_client = G2AApiClient()
                
                print("🔐 Получаем токен...")
                loop.run_until_complete(self.api_client.get_token())
                print("✅ Токен получен!")
                
                print("📊 Загружаем офферы...")
                result = loop.run_until_complete(self.api_client.get_offers())
                
                print(f"📊 Результат: {result.keys()}")
                
                if result.get("success"):
                    print("✅ Успешно получены офферы!")
                    
                    if result.get("offers_cache"):
                        offers_count = len(result["offers_cache"])
                        print(f"📊 Найдено {offers_count} офферов")
                        
                        first_offer = next(iter(result["offers_cache"].values()), None)
                        if first_offer and first_offer.get("seller_id"):
                            seller_id = first_offer.get("seller_id")
                            self.seller_id_var.set(seller_id)
                            g2a_config.G2A_SELLER_ID = seller_id
                            print(f"✅ Seller ID: {seller_id}")

                    self.offers_data = result.get("offers_cache", {})
                    
                    print("🔄 Обновляем таблицу...")
                    self.after(0, self.refresh_offers_table)
                    
                    success_msg = f"✅ Загружено {len(self.offers_data)} офферов"
                    print(success_msg)
                    messagebox.showinfo("Готово", success_msg)
                else:
                    error = result.get("error", "Неизвестная ошибка")
                    print(f"❌ Ошибка от API: {error}")
                    messagebox.showerror("Ошибка", error)
                    
            except Exception as e:
                print("
" + "="*60)
                print("❌ КРИТИЧЕСКАЯ ОШИБКА ПРИ ЗАГРУЗКЕ ОФФЕРОВ:")
                print(f"Тип ошибки: {type(e).__name__}")
                print(f"Сообщение: {str(e)}")
                print("
Полный traceback:")
                traceback.print_exc()
                print("="*60 + "\n")
                
                messagebox.showerror(
                    "Ошибка",
                    f"{type(e).__name__}: {str(e)}\n\nПроверьте консоль для деталей."
                )
            finally:
                if loop:
                    try:
                        loop.close()
                        print("✅ Event loop закрыт")
                    except:
                        pass

        threading.Thread(target=run, daemon=True).start()

# ... (остальной код без изменений)