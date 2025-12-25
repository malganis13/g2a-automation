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
import traceback

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

    def setup_settings_tab(self):
        """Вкладка настроек API"""
        frame = ctk.CTkFrame(self.tab_settings)
        frame.pack(fill="both", expand=True, padx=5, pady=5)

        scrollable = ctk.CTkScrollableFrame(frame, width=500, height=550)
        scrollable.pack(fill="both", expand=True, padx=5, pady=5)

        # G2A API Settings
        ctk.CTkLabel(scrollable, text="G2A API Настройки", font=("Arial", 11, "bold")).pack(pady=5)

        self.client_id_var = tk.StringVar()
        self.client_secret_var = tk.StringVar()
        self.client_email_var = tk.StringVar()

        ctk.CTkLabel(scrollable, text="G2A Client ID:", font=("Arial", 12)).pack(pady=5)
        self.client_id_entry = ctk.CTkEntry(scrollable, textvariable=self.client_id_var, width=400, height=26)
        self.client_id_entry.pack(pady=5)

        ctk.CTkLabel(scrollable, text="G2A Client Secret:", font=("Arial", 12)).pack(pady=5)
        self.client_secret_entry = ctk.CTkEntry(scrollable, textvariable=self.client_secret_var, width=400, height=26,
                                                show="*")
        self.client_secret_entry.pack(pady=5)

        ctk.CTkLabel(scrollable, text="G2A Account Email:", font=("Arial", 12)).pack(pady=5)
        self.client_email_entry = ctk.CTkEntry(scrollable, textvariable=self.client_email_var, width=400, height=26)
        self.client_email_entry.pack(pady=5)

        ctk.CTkLabel(scrollable, text="G2A Seller ID (автоматический):", font=("Arial", 12)).pack(pady=5)
        self.seller_id_entry = ctk.CTkEntry(scrollable, textvariable=self.seller_id_var, width=400, height=26, state="disabled")
        self.seller_id_entry.pack(pady=5)
        ctk.CTkLabel(scrollable, text="💡 ID получается автоматически при первой загрузке офферов", font=("Arial", 9), text_color="gray").pack(pady=3)

        # Разделитель
        ctk.CTkLabel(scrollable, text="─" * 60).pack(pady=20)

        # Telegram Settings
        ctk.CTkLabel(scrollable, text="Telegram Уведомления", font=("Arial", 11, "bold")).pack(pady=5)

        self.telegram_token_var = tk.StringVar()
        self.telegram_chat_var = tk.StringVar()

        ctk.CTkLabel(scrollable, text="Bot Token:", font=("Arial", 12)).pack(pady=5)
        self.telegram_token_entry = ctk.CTkEntry(scrollable, textvariable=self.telegram_token_var, width=400, height=26)
        self.telegram_token_entry.pack(pady=5)

        ctk.CTkLabel(scrollable, text="Chat ID:", font=("Arial", 12)).pack(pady=5)
        self.telegram_chat_entry = ctk.CTkEntry(scrollable, textvariable=self.telegram_chat_var, width=400, height=26)
        self.telegram_chat_entry.pack(pady=5)

        self.telegram_checkbox = ctk.CTkSwitch(
            scrollable,
            text="Включить Telegram уведомления",
            variable=self.telegram_enabled,
            font=("Arial", 10)
        )
        self.telegram_checkbox.pack(pady=5)

        # Кнопка сохранения
        ctk.CTkButton(
            scrollable,
            text="💾 Сохранить все настройки",
            command=self.save_all_settings,
            width=300,
            height=50,
            font=("Arial", 16, "bold"),
            fg_color="green",
            hover_color="darkgreen"
        ).pack(pady=10)

    def setup_auto_offers_tab(self):
        """
        ✅ НОВАЯ ВКЛАДКА: Объединённая "Автоизменение + Офферы"
        """
        main_container = ctk.CTkFrame(self.tab_auto)
        main_container.pack(fill="both", expand=True, padx=5, pady=5)

        # ========== ВЕРХНЯЯ ПАНЕЛЬ: Глобальные настройки ==========
        top_panel = ctk.CTkFrame(main_container, height=150)
        top_panel.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(top_panel, text="🤖 Глобальные настройки автоизменения", font=("Arial", 14, "bold")).pack(pady=5)

        controls_frame = ctk.CTkFrame(top_panel)
        controls_frame.pack(pady=5)

        # Статус
        self.auto_status_label = ctk.CTkLabel(
            controls_frame,
            text="🔴 Остановлено",
            font=("Arial", 13, "bold"),
            text_color="red"
        )
        self.auto_status_label.pack(side="left", padx=10)

        # Кнопки управления
        self.start_auto_btn = ctk.CTkButton(
            controls_frame,
            text="▶️ Запустить",
            command=self.start_auto_price_changing,
            width=150,
            height=40,
            fg_color="green",
            hover_color="darkgreen"
        )
        self.start_auto_btn.pack(side="left", padx=5)

        self.stop_auto_btn = ctk.CTkButton(
            controls_frame,
            text="⏹️ Остановить",
            command=self.stop_auto_price_changing,
            width=150,
            height=40,
            fg_color="red",
            hover_color="darkred",
            state="disabled"
        )
        self.stop_auto_btn.pack(side="left", padx=5)

        ctk.CTkButton(
            controls_frame,
            text="⚙️ Настроить",
            command=self.open_auto_settings_dialog,
            width=150,
            height=40
        ).pack(side="left", padx=5)

        # ========== СРЕДНЯЯ ЧАСТЬ: Таблица офферов ==========
        middle_container = ctk.CTkFrame(main_container)
        middle_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Левая часть - таблица
        left_frame = ctk.CTkFrame(middle_container)
        left_frame.pack(side="left", fill="both", expand=True, padx=5)

        ctk.CTkLabel(left_frame, text="📋 Список офферов", font=("Arial", 12, "bold")).pack(pady=5)

        # Поиск и кнопки
        search_frame = ctk.CTkFrame(left_frame)
        search_frame.pack(pady=5, padx=5, fill="x")

        ctk.CTkLabel(search_frame, text="🔍 Поиск:", font=("Arial", 11)).pack(side="left", padx=5)
        self.search_var.trace("w", self.filter_offers)
        search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var, width=200, height=30)
        search_entry.pack(side="left", padx=5)

        ctk.CTkButton(
            search_frame,
            text="🔄 Обновить",
            command=self.load_offers,
            width=120,
            height=35
        ).pack(side="left", padx=5)

        # ✅ ТАБЛИЦА С ЧЕКБОКСАМИ
        table_frame = ctk.CTkFrame(left_frame)
        table_frame.pack(fill="both", expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(table_frame)
        scrollbar.pack(side="right", fill="y")

        # Колонки: ☑️ | Игра | Ваша цена | Конкурент | Порог | Авто
        self.offers_tree = ttk.Treeview(
            table_frame,
            columns=("Select", "Game", "YourPrice", "Competitor", "Threshold", "Auto", "Stock"),
            show="headings",
            height=20,
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.offers_tree.yview)

        self.offers_tree.heading("Select", text="☑")
        self.offers_tree.heading("Game", text="Игра")
        self.offers_tree.heading("YourPrice", text="Ваша цена")
        self.offers_tree.heading("Competitor", text="Конкурент")
        self.offers_tree.heading("Threshold", text="Порог")
        self.offers_tree.heading("Auto", text="Авто")
        self.offers_tree.heading("Stock", text="Склад")

        self.offers_tree.column("Select", width=40)
        self.offers_tree.column("Game", width=300)
        self.offers_tree.column("YourPrice", width=100)
        self.offers_tree.column("Competitor", width=100)
        self.offers_tree.column("Threshold", width=100)
        self.offers_tree.column("Auto", width=80)
        self.offers_tree.column("Stock", width=80)

        self.offers_tree.pack(fill="both", expand=True)

        # Bind событий
        self.offers_tree.bind("<Button-1>", self.on_tree_click)
        self.offers_tree.bind("<<TreeviewSelect>>", self.on_offer_select)

        # Правая часть - управление
        right_frame = ctk.CTkFrame(middle_container, width=400)
        right_frame.pack(side="right", fill="both", padx=5)

        ctk.CTkLabel(right_frame, text="🎯 Управление оффером", font=("Arial", 12, "bold")).pack(pady=5)

        # Информация о выбранном
        self.selected_offer_label = ctk.CTkLabel(
            right_frame,
            text="Выберите оффер из списка",
            font=("Arial", 10),
            wraplength=350,
            justify="left"
        )
        self.selected_offer_label.pack(pady=10, padx=10)

        # Scrollable для кнопок
        scrollable_right = ctk.CTkScrollableFrame(right_frame, width=360, height=500)
        scrollable_right.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(scrollable_right, text="Точечные операции:", font=("Arial", 11, "bold")).pack(pady=5)

        ctk.CTkButton(
            scrollable_right,
            text="🔄 Обновить цену конкурента",
            command=self.update_competitor_price,
            width=250,
            height=45
        ).pack(pady=5)

        ctk.CTkButton(
            scrollable_right,
            text="🛡️ Установить минимальный порог",
            command=self.set_threshold_for_selected,
            width=250,
            height=45
        ).pack(pady=5)

        self.auto_toggle_btn = ctk.CTkButton(
            scrollable_right,
            text="🤖 Вкл/Выкл автоизменение",
            command=self.toggle_auto_for_offer,
            width=250,
            height=45
        )
        self.auto_toggle_btn.pack(pady=5)

        ctk.CTkButton(
            scrollable_right,
            text="💰 Изменить цену вручную",
            command=self.change_selected_offer_price,
            width=250,
            height=45
        ).pack(pady=5)

        ctk.CTkLabel(scrollable_right, text="─" * 30).pack(pady=10)
        ctk.CTkLabel(scrollable_right, text="Массовые операции:", font=("Arial", 11, "bold")).pack(pady=5)

        ctk.CTkButton(
            scrollable_right,
            text="☑️ Включить авто для выбранных",
            command=lambda: self.mass_toggle_auto(True),
            width=250,
            height=45,
            fg_color="green"
        ).pack(pady=5)

        ctk.CTkButton(
            scrollable_right,
            text="☐ Выключить авто для выбранных",
            command=lambda: self.mass_toggle_auto(False),
            width=250,
            height=45,
            fg_color="orange"
        ).pack(pady=5)

        ctk.CTkButton(
            scrollable_right,
            text="🛡️ Установить порог для выбранных",
            command=self.set_threshold_for_selected_mass,
            width=250,
            height=45
        ).pack(pady=5)

    def setup_parsing_tab(self):
        """Вкладка парсинга"""
        frame = ctk.CTkFrame(self.tab_parsing)
        frame.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(frame, text="Парсинг цен G2A", font=("Arial", 11, "bold")).pack(pady=20)

        btn_frame = ctk.CTkFrame(frame)
        btn_frame.pack(pady=20)

        ctk.CTkButton(
            btn_frame,
            text="📊 Обычный парсинг цен",
            command=lambda: self.run_parsing(auto_sell=False),
            width=280,
            height=70,
            font=("Arial", 15)
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame,
            text="🚀 Парсинг + автовыставление",
            command=lambda: self.run_parsing(auto_sell=True),
            width=280,
            height=70,
            font=("Arial", 15)
        ).pack(side="left", padx=10)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ctk.CTkProgressBar(frame, variable=self.progress_var, width=500, height=16)
        self.progress_bar.pack(pady=20)
        self.progress_bar.set(0)

        self.log_text = ctk.CTkTextbox(frame, width=680, height=380, font=("Courier", 8))
        self.log_text.pack(pady=20)

    def setup_keys_tab(self):
        """Вкладка ключей"""
        frame = ctk.CTkFrame(self.tab_keys)
        frame.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(frame, text="Управление ключами", font=("Arial", 11, "bold")).pack(pady=20)

        btn_frame = ctk.CTkFrame(frame)
        btn_frame.pack(pady=10)

        ctk.CTkButton(
            btn_frame,
            text="📁 Добавить ключи из файла",
            command=self.add_keys_from_file,
            width=250,
            height=60
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame,
            text="📂 Добавить из папки",
            command=self.add_keys_from_folder,
            width=250,
            height=60
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame,
            text="📊 Обновить статистику",
            command=self.show_keys_stats,
            width=250,
            height=60
        ).pack(side="left", padx=10)

        self.stats_scrollable = ctk.CTkScrollableFrame(frame, width=750, height=520)
        self.stats_scrollable.pack(pady=20, fill="both", expand=True)

        self.stats_label = ctk.CTkLabel(
            self.stats_scrollable,
            text="Нажмите 'Обновить статистику' для загрузки...",
            font=("Courier", 9),
            justify="left",
            anchor="w"
        )
        self.stats_label.pack(pady=20, padx=20, fill="both")

    def setup_stats_tab(self):
        """Вкладка статистики"""
        frame = ctk.CTkFrame(self.tab_stats)
        frame.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(frame, text="Статистика изменений цен", font=("Arial", 11, "bold")).pack(pady=20)

        period_frame = ctk.CTkFrame(frame)
        period_frame.pack(pady=10)

        ctk.CTkButton(
            period_frame,
            text="За сегодня",
            command=lambda: self.load_price_stats("day"),
            width=160,
            height=45
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            period_frame,
            text="За 7 дней",
            command=lambda: self.load_price_stats("week"),
            width=160,
            height=45
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            period_frame,
            text="За 30 дней",
            command=lambda: self.load_price_stats("month"),
            width=160,
            height=45
        ).pack(side="left", padx=5)

        self.stats_text = ctk.CTkTextbox(frame, width=700, height=480, font=("Courier", 8))
        self.stats_text.pack(pady=20)

    # ==================== МЕТОДЫ ====================

    def load_all_configs(self):
        """Загрузка всех конфигураций при старте"""
        self.client_id_var.set(g2a_config.G2A_CLIENT_ID)
        self.client_secret_var.set(g2a_config.G2A_CLIENT_SECRET)
        self.client_email_var.set(g2a_config.G2A_CLIENT_EMAIL)
        self.telegram_token_var.set(g2a_config.TELEGRAM_BOT_TOKEN)
        self.telegram_chat_var.set(g2a_config.TELEGRAM_CHAT_ID)
        self.seller_id_var.set(g2a_config.G2A_SELLER_ID)
        print("✅ Настройки загружены")

    def save_all_settings(self):
        """Сохранение всех настроек"""
        client_id = self.client_id_var.get().strip()
        client_secret = self.client_secret_var.get().strip()
        client_email = self.client_email_var.get().strip()
        telegram_token = self.telegram_token_var.get().strip()
        telegram_chat = self.telegram_chat_var.get().strip()

        if not client_id or not client_secret or not client_email:
            messagebox.showerror("Ошибка", "Заполните все обязательные поля G2A")
            return

        config_data = {
            "G2A_CLIENT_ID": client_id,
            "G2A_CLIENT_SECRET": client_secret,
            "G2A_CLIENT_EMAIL": client_email,
            "G2A_SELLER_ID": self.seller_id_var.get(),
            "TELEGRAM_BOT_TOKEN": telegram_token,
            "TELEGRAM_CHAT_ID": telegram_chat,
            "TELEGRAM_ENABLED": self.telegram_enabled.get()
        }

        try:
            with open("g2a_config_saved.json", "w", encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)

            g2a_config.reload_config()

            if telegram_token and telegram_chat:
                from telegram_notifier import notifier
                notifier.update_credentials(telegram_token, telegram_chat)

            messagebox.showinfo("Успех", "✅ Настройки сохранены!")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить: {e}")

    def load_offers(self):
        """✅ ИСПРАВЛЕНО: Загрузка офферов с детальным логированием"""
        print("\n" + "="*60)
        print("🔄 НАЧАЛО ЗАГРУЗКИ ОФФЕРОВ")
        print("="*60)
        
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                print("📡 Шаг 1: Создание API клиента...")
                self.api_client = G2AApiClient()
                
                print("🔑 Шаг 2: Получение токена авторизации...")
                loop.run_until_complete(self.api_client.get_token())
                print("✅ Токен получен успешно")
                
                print("📦 Шаг 3: Запрос списка офферов...")
                result = loop.run_until_complete(self.api_client.get_offers())
                
                print(f"📊 Получен результат: success={result.get('success')}")
                
                if result.get("success"):
                    print("✅ Офферы успешно получены")
                    
                    # Извлекаем seller_id
                    if result.get("offers_cache"):
                        first_offer = next(iter(result["offers_cache"].values()), None)
                        if first_offer and first_offer.get("seller_id"):
                            seller_id = first_offer.get("seller_id")
                            self.seller_id_var.set(seller_id)
                            g2a_config.G2A_SELLER_ID = seller_id
                            print(f"✅ Seller ID установлен: {seller_id}")

                    self.offers_data = result.get("offers_cache", {})
                    print(f"📦 Всего офферов загружено: {len(self.offers_data)}")
                    
                    # Обновляем таблицу
                    print("🔄 Обновление таблицы GUI...")
                    self.refresh_offers_table()
                    print("✅ Таблица обновлена")
                    
                    messagebox.showinfo("Готово", f"✅ Загружено {len(self.offers_data)} офферов")
                    print("="*60)
                    print("✅ ЗАГРУЗКА ОФФЕРОВ ЗАВЕРШЕНА")
                    print("="*60 + "\n")
                else:
                    error_msg = result.get("error", "Неизвестная ошибка")
                    print(f"❌ ОШИБКА API: {error_msg}")
                    messagebox.showerror("Ошибка API", f"Не удалось загрузить офферы:\n\n{error_msg}")
                    
            except Exception as e:
                print(f"\n{'='*60}")
                print("❌ КРИТИЧЕСКАЯ ОШИБКА")
                print(f"{'='*60}")
                print(f"Тип ошибки: {type(e).__name__}")
                print(f"Сообщение: {str(e)}")
                print("\nПолный traceback:")
                traceback.print_exc()
                print(f"{'='*60}\n")
                
                messagebox.showerror(
                    "Критическая ошибка",
                    f"Не удалось загрузить офферы:\n\n{type(e).__name__}: {str(e)}\n\nПроверьте консоль для подробностей"
                )
            finally:
                print("🔄 Закрытие event loop...")
                loop.close()
                print("✅ Event loop закрыт\n")

        print("🚀 Запуск в отдельном потоке...")
        threading.Thread(target=run, daemon=True).start()

    def refresh_offers_table(self):
        """✅ Обновить таблицу офферов"""
        for item in self.offers_tree.get_children():
            self.offers_tree.delete(item)

        for product_id, info in self.offers_data.items():
            # Получаем настройки из БД
            settings = self.db.get_product_settings(product_id)
            
            threshold = settings.get("min_floor_price") if settings else None
            threshold_str = f"€{threshold:.2f}" if threshold else "-"
            
            auto_enabled = bool(settings.get("auto_enabled", 0)) if settings else False
            auto_str = "🟢" if auto_enabled else "🔴"
            
            # Цена конкурента
            comp_price = self.competitor_prices.get(product_id)
            comp_str = f"€{comp_price:.2f}" if comp_price else "?"
            
            # Чекбокс
            select_mark = "☑" if product_id in self.selected_offers else "☐"
            
            self.offers_tree.insert("", "end", values=(
                select_mark,
                info.get("product_name", "N/A"),
                f"€{info.get('price', 0)}",
                comp_str,
                threshold_str,
                auto_str,
                info.get("current_stock", 0)
            ), tags=(product_id,))

    def filter_offers(self, *args):
        """Фильтрация офферов по поисковому запросу"""
        search_query = self.search_var.get().lower()
        
        for item in self.offers_tree.get_children():
            self.offers_tree.delete(item)

        for product_id, info in self.offers_data.items():
            game_name = info.get("product_name", "").lower()
            
            if not search_query or search_query in game_name:
                settings = self.db.get_product_settings(product_id)
                threshold = settings.get("min_floor_price") if settings else None
                threshold_str = f"€{threshold:.2f}" if threshold else "-"
                auto_enabled = bool(settings.get("auto_enabled", 0)) if settings else False
                auto_str = "🟢" if auto_enabled else "🔴"
                comp_price = self.competitor_prices.get(product_id)
                comp_str = f"€{comp_price:.2f}" if comp_price else "?"
                select_mark = "☑" if product_id in self.selected_offers else "☐"
                
                self.offers_tree.insert("", "end", values=(
                    select_mark,
                    info.get("product_name", "N/A"),
                    f"€{info.get('price', 0)}",
                    comp_str,
                    threshold_str,
                    auto_str,
                    info.get("current_stock", 0)
                ), tags=(product_id,))

    def on_tree_click(self, event):
        """✅ Обработка клика по чекбоксу"""
        region = self.offers_tree.identify("region", event.x, event.y)
        
        if region == "cell":
            column = self.offers_tree.identify_column(event.x)
            
            if column == "#1":  # Колонка с чекбоксом
                item = self.offers_tree.identify_row(event.y)
                if item:
                    tags = self.offers_tree.item(item, "tags")
                    if tags:
                        product_id = tags[0]
                        
                        if product_id in self.selected_offers:
                            self.selected_offers.remove(product_id)
                        else:
                            self.selected_offers.add(product_id)
                        
                        self.refresh_offers_table()

    def on_offer_select(self, event):
        """✅ Выбор оффера - показ детальной информации"""
        selection = self.offers_tree.selection()
        if not selection:
            return

        item = self.offers_tree.item(selection[0])
        tags = item.get('tags')
        
        if not tags:
            return
        
        product_id = tags[0]
        offer_info = self.offers_data.get(product_id)
        
        if not offer_info:
            return

        # Получаем настройки
        settings = self.db.get_product_settings(product_id)
        threshold = settings.get("min_floor_price") if settings else None
        auto_enabled = bool(settings.get("auto_enabled", 0)) if settings else False
        
        # Цена конкурента
        comp_price = self.competitor_prices.get(product_id)
        
        info_text = f"""
📋 Выбранный оффер:

🎮 Игра:
{offer_info.get('product_name', 'N/A')}

💰 Ваша цена: €{offer_info.get('price', 0):.2f}
🏆 Конкурент: {f'€{comp_price:.2f}' if comp_price else '❓ (обновите)'}
🛡️ Порог: {f'€{threshold:.2f}' if threshold else '❌ (не установлен)'}
📦 Склад: {offer_info.get('current_stock', 0)}

🤖 Автоизменение: {'🟢 ВКЛЮЧЕНО' if auto_enabled else '🔴 ВЫКЛЮЧЕНО'}
"""

        self.selected_offer_label.configure(text=info_text)

    def update_competitor_price(self):
        """✅ Обновить цену конкурента для выбранного оффера"""
        selection = self.offers_tree.selection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите оффер")
            return

        item = self.offers_tree.item(selection[0])
        tags = item.get('tags')
        if not tags:
            return
        
        product_id = tags[0]
        
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if not self.api_client:
                    self.api_client = G2AApiClient()
                    loop.run_until_complete(self.api_client.get_token())
                
                result = loop.run_until_complete(
                    self.api_client.get_competitor_min_price(product_id)
                )
                
                if result.get("success"):
                    min_price = result.get("min_price")
                    if min_price:
                        self.competitor_prices[product_id] = min_price
                        self.refresh_offers_table()
                        messagebox.showinfo("Успех", f"Цена конкурента: €{min_price:.2f}")
                    else:
                        messagebox.showinfo("Инфо", "Нет конкурентов для этого товара")
                else:
                    messagebox.showerror("Ошибка", result.get("error"))
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))
            finally:
                loop.close()

        threading.Thread(target=run, daemon=True).start()

    def set_threshold_for_selected(self):
        """✅ Установить порог для выбранного оффера"""
        selection = self.offers_tree.selection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите оффер")
            return

        item = self.offers_tree.item(selection[0])
        tags = item.get('tags')
        if not tags:
            return
        
        product_id = tags[0]
        offer_info = self.offers_data.get(product_id)
        
        threshold = simpledialog.askfloat(
            "Установить порог",
            f"Установите минимальный порог для:\n{offer_info.get('product_name')}\n\nМинимальная цена (EUR):",
            minvalue=0.01,
            maxvalue=1000.0
        )
        
        if threshold:
            self.db.set_product_settings(
                product_id=product_id,
                game_name=offer_info.get('product_name'),
                min_floor_price=threshold
            )
            self.refresh_offers_table()
            messagebox.showinfo("Успех", f"✅ Порог установлен: €{threshold:.2f}")

    def set_threshold_for_selected_mass(self):
        """✅ Массовая установка порога"""
        if not self.selected_offers:
            messagebox.showwarning("Внимание", "Выберите офферы (чекбоксы)")
            return
        
        threshold = simpledialog.askfloat(
            "Массовая установка порога",
            f"Установить порог для {len(self.selected_offers)} офферов:\n\nМинимальная цена (EUR):",
            minvalue=0.01,
            maxvalue=1000.0
        )
        
        if threshold:
            for product_id in self.selected_offers:
                offer_info = self.offers_data.get(product_id)
                if offer_info:
                    self.db.set_product_settings(
                        product_id=product_id,
                        game_name=offer_info.get('product_name'),
                        min_floor_price=threshold
                    )
            
            self.refresh_offers_table()
            messagebox.showinfo("Успех", f"✅ Порог €{threshold:.2f} установлен для {len(self.selected_offers)} офферов")

    def toggle_auto_for_offer(self):
        """✅ Включить/выключить автоизменение"""
        selection = self.offers_tree.selection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите оффер")
            return

        item = self.offers_tree.item(selection[0])
        tags = item.get('tags')
        if not tags:
            return
        
        product_id = tags[0]
        offer_info = self.offers_data.get(product_id)
        
        settings = self.db.get_product_settings(product_id)
        current_state = bool(settings.get("auto_enabled", 0)) if settings else False
        
        new_state = not current_state
        
        self.db.set_product_settings(
            product_id=product_id,
            game_name=offer_info.get('product_name'),
            auto_enabled=1 if new_state else 0
        )
        
        self.refresh_offers_table()
        self.on_offer_select(None)
        
        status = "ВКЛЮЧЕНО" if new_state else "ВЫКЛЮЧЕНО"
        messagebox.showinfo("Успех", f"✅ Автоизменение {status}")

    def mass_toggle_auto(self, enabled):
        """✅ Массовое включение/выключение автоизменения"""
        if not self.selected_offers:
            messagebox.showwarning("Внимание", "Выберите офферы (чекбоксы)")
            return
        
        for product_id in self.selected_offers:
            offer_info = self.offers_data.get(product_id)
            if offer_info:
                self.db.set_product_settings(
                    product_id=product_id,
                    game_name=offer_info.get('product_name'),
                    auto_enabled=1 if enabled else 0
                )
        
        self.refresh_offers_table()
        status = "ВКЛЮЧЕНО" if enabled else "ВЫКЛЮЧЕНО"
        messagebox.showinfo("Успех", f"✅ Автоизменение {status} для {len(self.selected_offers)} офферов")

    def change_selected_offer_price(self):
        """Изменить цену оффера вручную"""
        selection = self.offers_tree.selection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите оффер")
            return

        item = self.offers_tree.item(selection[0])
        tags = item.get('tags')
        if not tags:
            return
        
        product_id = tags[0]
        offer_info = self.offers_data.get(product_id)
        
        new_price = simpledialog.askfloat(
            "Изменение цены",
            f"Текущая цена: €{offer_info.get('price', 0):.2f}\n\nВведите новую цену (EUR):",
            minvalue=0.01,
            maxvalue=1000.0
        )

        if new_price is None:
            return

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                api_client = G2AApiClient()
                loop.run_until_complete(api_client.get_token())
                
                update_data = {
                    "offerType": offer_info.get('offer_type', 'dropshipping'),
                    "variant": {
                        "price": {
                            "retail": str(new_price),
                            "business": str(new_price)
                        },
                        "active": True
                    }
                }

                result = loop.run_until_complete(
                    api_client.update_offer_partial(offer_info.get('id'), update_data)
                )

                if result.get("success"):
                    messagebox.showinfo("Успех", f"✅ Цена обновлена на €{new_price:.2f}")
                    self.after(100, self.load_offers)
                else:
                    messagebox.showerror("Ошибка", result.get("error"))
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))
            finally:
                try:
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    loop.run_until_complete(asyncio.sleep(0.1))
                except:
                    pass
                finally:
                    loop.close()

        threading.Thread(target=run, daemon=True).start()

    def open_auto_settings_dialog(self):
        """✅ Диалог настроек автоизменения"""
        from auto_price_changer import AutoPriceSettings
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("⚙️ Настройки автоизменения")
        dialog.geometry("500x600")
        
        settings = AutoPriceSettings()
        
        frame = ctk.CTkScrollableFrame(dialog, width=450, height=550)
        frame.pack(padx=10, pady=10, fill="both", expand=True)
        
        # Включение
        enabled_var = tk.BooleanVar(value=settings.settings.get("enabled", False))
        ctk.CTkSwitch(
            frame,
            text="🤖 Включить глобальное автоизменение",
            variable=enabled_var,
            font=("Arial", 12, "bold")
        ).pack(pady=10)
        
        # Интервал
        ctk.CTkLabel(frame, text="Интервал проверки (секунды):", font=("Arial", 11)).pack(pady=5)
        interval_var = tk.IntVar(value=settings.settings.get("check_interval", 1800))
        ctk.CTkEntry(frame, textvariable=interval_var, width=200).pack(pady=5)
        
        # Снижение
        ctk.CTkLabel(frame, text="Снижение от конкурента (EUR):", font=("Arial", 11)).pack(pady=5)
        undercut_var = tk.DoubleVar(value=settings.settings.get("undercut_amount", 0.01))
        ctk.CTkEntry(frame, textvariable=undercut_var, width=200).pack(pady=5)
        
        # Глобальный минимум
        ctk.CTkLabel(frame, text="Глобальный минимум (EUR):", font=("Arial", 11)).pack(pady=5)
        min_price_var = tk.DoubleVar(value=settings.settings.get("min_price", 0.1))
        ctk.CTkEntry(frame, textvariable=min_price_var, width=200).pack(pady=5)
        
        # Максимум
        ctk.CTkLabel(frame, text="Максимум (EUR):", font=("Arial", 11)).pack(pady=5)
        max_price_var = tk.DoubleVar(value=settings.settings.get("max_price", 100.0))
        ctk.CTkEntry(frame, textvariable=max_price_var, width=200).pack(pady=5)
        
        # Дневной лимит
        ctk.CTkLabel(frame, text="Дневной лимит изменений:", font=("Arial", 11)).pack(pady=5)
        daily_limit_var = tk.IntVar(value=settings.settings.get("daily_limit", 20))
        ctk.CTkEntry(frame, textvariable=daily_limit_var, width=200).pack(pady=5)
        
        # Telegram
        telegram_var = tk.BooleanVar(value=settings.settings.get("telegram_notifications", False))
        ctk.CTkSwitch(
            frame,
            text="📱 Telegram уведомления",
            variable=telegram_var,
            font=("Arial", 11)
        ).pack(pady=10)
        
        def save():
            settings.settings.update({
                "enabled": enabled_var.get(),
                "check_interval": interval_var.get(),
                "undercut_amount": undercut_var.get(),
                "min_price": min_price_var.get(),
                "max_price": max_price_var.get(),
                "daily_limit": daily_limit_var.get(),
                "telegram_notifications": telegram_var.get()
            })
            settings.save_settings()
            messagebox.showinfo("Успех", "✅ Настройки сохранены!")
            dialog.destroy()
        
        ctk.CTkButton(
            frame,
            text="💾 Сохранить",
            command=save,
            width=200,
            height=45,
            font=("Arial", 14, "bold"),
            fg_color="green"
        ).pack(pady=20)

    def start_auto_price_changing(self):
        """Запуск автоизменения"""
        if self.auto_running:
            messagebox.showwarning("Внимание", "Автоизменение уже запущено!")
            return

        g2a_config.reload_config()
        if not g2a_config.G2A_CLIENT_ID or not g2a_config.G2A_CLIENT_SECRET:
            messagebox.showerror("Ошибка", "Заполните данные G2A API в настройках!")
            return

        def run_auto():
            import auto_price_changer
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            self.auto_running = True
            self.auto_status_label.configure(text="🟢 Работает", text_color="green")
            self.start_auto_btn.configure(state="disabled")
            self.stop_auto_btn.configure(state="normal")

            try:
                self.auto_changer = auto_price_changer.AutoPriceChanger()
                loop.run_until_complete(self.auto_changer.start())
            except Exception as e:
                print(f"❌ Ошибка: {e}")
            finally:
                self.auto_running = False
                self.auto_changer = None
                self.auto_status_label.configure(text="🔴 Остановлено", text_color="red")
                self.start_auto_btn.configure(state="normal")
                self.stop_auto_btn.configure(state="disabled")
                loop.close()

        self.auto_process = threading.Thread(target=run_auto, daemon=True)
        self.auto_process.start()

    def stop_auto_price_changing(self):
        """Остановка автоизменения"""
        if not self.auto_running:
            messagebox.showinfo("Инфо", "Автоизменение не запущено")
            return

        if hasattr(self, 'auto_changer') and self.auto_changer:
            self.auto_changer.stop()
            self.stop_auto_btn.configure(state="disabled")
            messagebox.showinfo("Инфо", "Автоизменение остановлено")

    def run_parsing(self, auto_sell=False):
        """Запуск парсинга"""
        def parse():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            self.log("🚀 Начинаем парсинг...")
            self.progress_bar.set(0.1)

            try:
                loop.run_until_complete(self.price_parser.process_files(auto_sell=auto_sell))
                self.progress_bar.set(1.0)
                self.log("✅ Парсинг завершен!")
                messagebox.showinfo("Готово", "Парсинг завершен!")
            except Exception as e:
                self.log(f"❌ Ошибка: {e}")
                messagebox.showerror("Ошибка", str(e))
            finally:
                self.progress_bar.set(0)
                loop.close()

        threading.Thread(target=parse, daemon=True).start()

    def log(self, msg):
        """Лог парсинга"""
        self.log_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see("end")

    def add_keys_from_file(self):
        """Добавить ключи из файла"""
        file_path = filedialog.askopenfilename(
            title="Выберите файл",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        if file_path:
            added = self.key_manager.add_keys_from_file(file_path)
            messagebox.showinfo("Готово", f"Добавлено {added} ключей")
            self.show_keys_stats()

    def add_keys_from_folder(self):
        """Добавить из папки"""
        folder = filedialog.askdirectory(title="Выберите папку")

        if folder:
            results = self.key_manager.add_keys_from_folder(folder)
            total = sum(results.values())
            messagebox.showinfo("Готово", f"Добавлено {total} ключей")
            self.show_keys_stats()

    def show_keys_stats(self):
        """Показать статистику ключей"""
        stats = self.key_manager.get_keys_stats()
        games = self.key_manager.get_games_list()

        text = f"""
╔════════════════════════════════════════╗
║         📊 СТАТИСТИКА КЛЮЧЕЙ          ║
╚════════════════════════════════════════╝

📦 Всего:           {stats.get('total', 0)}
✅ Доступно:        {stats.get('available', 0)}
💰 Продано:         {stats.get('sold', 0)}
🔒 Зарезервировано: {stats.get('reserved', 0)}

╔════════════════════════════════════════╗
║         🎮 ИГР В БАЗЕ: {len(games):<4}          ║
╚════════════════════════════════════════╝

ТОП-20 ИГР:

"""

        for i, g in enumerate(games[:20], 1):
            text += f"{i:2}. {g['name']}\n"
            text += f"    Ключей: {g['available_keys']}/{g['total_keys']}"
            text += f" | €{g['min_price']:.2f}-€{g['max_price']:.2f}\n\n"

        if len(games) > 20:
            text += f"\n... и еще {len(games) - 20} игр\n"

        self.stats_label.configure(text=text)

    def load_price_stats(self, period):
        """Статистика цен"""
        period_map = {"day": 1, "week": 7, "month": 30}
        days = period_map.get(period, 1)
        
        try:
            stats = self.db.get_price_changes_stats(days)
            
            self.stats_text.delete("1.0", "end")
            
            output = f"""
╔════════════════════════════════════════════════════════╗
║  📊 СТАТИСТИКА ИЗМЕНЕНИЙ ЦЕН - {stats['period']}
╚════════════════════════════════════════════════════════╝

📈 ОБЩАЯ СВОДКА:
───────────────────────────────────────────────────────────
    Всего изменений цен:     {stats['summary']['total_changes']}
    📉 Понижений цен:         {stats['summary']['price_decreases']}
    📈 Повышений цен:         {stats['summary']['price_increases']}
    💰 Среднее изменение:     €{stats['summary']['avg_price_change']:.2f}
    💸 Общее изменение:       €{stats['summary']['total_price_change']:.2f}
    🕐 Изменений сегодня:     {stats['summary']['today_changes']}

"""

            if stats.get('top_changed_games'):
                output += """
╔════════════════════════════════════════════════════════╗
║  🎮 ТОП-20 ИГР С НАИБОЛЬШИМИ ИЗМЕНЕНИЯМИ
╚════════════════════════════════════════════════════════╝

"""
                for idx, game in enumerate(stats['top_changed_games'], 1):
                    output += f"""
{idx}. {game['game_name']}
    Изменений: {game['change_count']}
    Мин. старая цена: €{game['min_old_price']:.2f}
    Макс. новая цена: €{game['max_new_price']:.2f}
    Среднее изменение: €{game['avg_change']:.2f}
"""

            self.stats_text.insert("1.0", output)
            
        except Exception as e:
            self.stats_text.delete("1.0", "end")
            error_msg = f"❌ ОШИБКА: {str(e)}"
            self.stats_text.insert("1.0", error_msg)


def main():
    app = G2AAutomationGUI()
    app.mainloop()


if __name__ == "__main__":
    main()