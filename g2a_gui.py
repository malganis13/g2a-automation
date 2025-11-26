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
        self.geometry("1100x750")

        # Инициализация компонентов
        self.key_manager = KeyManager()
        self.price_parser = KeyPriceParser()
        self.db = PriceDatabase()
        self.api_client = None

        # Переменные настроек
        self.telegram_enabled = tk.BooleanVar(value=False)

        # Для хранения данных офферов
        self.offers_data = {}

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
        self.tabview = ctk.CTkTabview(self, width=1050, height=700)
        self.tabview.pack(padx=5, pady=5, fill="both", expand=True)

        # Создание вкладок
        self.tab_settings = self.tabview.add("⚙️ Настройки")
        self.tab_auto = self.tabview.add("🤖 Автоизменение")
        self.tab_parsing = self.tabview.add("📊 Парсинг")
        self.tab_offers = self.tabview.add("🎮 Офферы")
        self.tab_keys = self.tabview.add("🔑 Ключи")
        self.tab_stats = self.tabview.add("📈 Статистика")

        self.setup_settings_tab()
        self.setup_auto_tab()
        self.setup_parsing_tab()
        self.setup_offers_tab()
        self.setup_keys_tab()
        self.setup_stats_tab()

    def setup_settings_tab(self):
        """Вкладка настроек API (БЕЗ минимальной цены)"""
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

    def setup_auto_tab(self):
        """Вкладка автоматического изменения цен"""
        frame = ctk.CTkFrame(self.tab_auto)
        frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Левая панель - настройки
        left_frame = ctk.CTkFrame(frame, width=500)
        left_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        scrollable = ctk.CTkScrollableFrame(left_frame, width=320, height=520)
        scrollable.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(scrollable, text="Настройки автоизменения", font=("Arial", 11, "bold")).pack(pady=5)

        # Главный переключатель
        self.auto_enabled_var = tk.BooleanVar(value=False)
        ctk.CTkSwitch(
            scrollable,
            text="🤖 Включить автоматическое изменение цен",
            variable=self.auto_enabled_var,
            font=("Arial", 11, "bold")
        ).pack(pady=5)

        # Telegram для авто
        self.auto_telegram_var = tk.BooleanVar(value=False)
        ctk.CTkSwitch(
            scrollable,
            text="📱 Telegram уведомления",
            variable=self.auto_telegram_var,
            font=("Arial", 10)
        ).pack(pady=10)

        # Интервал
        ctk.CTkLabel(scrollable, text="Интервал проверки:", font=("Arial", 13, "bold")).pack(pady=10)
        self.auto_interval_var = tk.IntVar(value=1800)

        interval_frame = ctk.CTkFrame(scrollable)
        interval_frame.pack(pady=5)

        interval_slider = ctk.CTkSlider(
            interval_frame,
            from_=300,
            to=7200,
            variable=self.auto_interval_var,
            width=300
        )
        interval_slider.pack(side="left", padx=5)

        self.interval_label = ctk.CTkLabel(interval_frame, text="30 мин", width=80)
        self.interval_label.pack(side="left", padx=5)

        def update_interval(value):
            minutes = int(float(value)) // 60
            self.interval_label.configure(text=f"{minutes} мин")

        interval_slider.configure(command=update_interval)

        # Снижение цены
        ctk.CTkLabel(scrollable, text="Снижение относительно конкурента (EUR):", font=("Arial", 13, "bold")).pack(
            pady=10)
        self.auto_undercut_var = tk.DoubleVar(value=0.01)
        ctk.CTkEntry(scrollable, textvariable=self.auto_undercut_var, width=150).pack(pady=5)

        # Мин/макс цена
        price_frame = ctk.CTkFrame(scrollable)
        price_frame.pack(pady=10)

        ctk.CTkLabel(price_frame, text="Мин. цена:", font=("Arial", 12)).pack(side="left", padx=5)
        self.auto_min_price_var = tk.DoubleVar(value=0.1)
        ctk.CTkEntry(price_frame, textvariable=self.auto_min_price_var, width=100).pack(side="left", padx=5)

        ctk.CTkLabel(price_frame, text="Макс. цена:", font=("Arial", 12)).pack(side="left", padx=5)
        self.auto_max_price_var = tk.DoubleVar(value=100.0)
        ctk.CTkEntry(price_frame, textvariable=self.auto_max_price_var, width=100).pack(side="left", padx=5)

        # Дневной лимит
        ctk.CTkLabel(scrollable, text="Максимум изменений в день:", font=("Arial", 13, "bold")).pack(pady=10)
        self.auto_daily_limit_var = tk.IntVar(value=20)
        ctk.CTkEntry(scrollable, textvariable=self.auto_daily_limit_var, width=150).pack(pady=5)

        # Кнопки
        btn_frame = ctk.CTkFrame(scrollable)
        btn_frame.pack(pady=20)

        ctk.CTkButton(
            btn_frame,
            text="💾 Сохранить настройки",
            command=self.save_auto_settings,
            width=180,
            height=45,
            font=("Arial", 13, "bold")
        ).pack(pady=5)

        # Правая панель - управление и статус
        right_frame = ctk.CTkFrame(frame, width=700)
        right_frame.pack(side="right", fill="both", padx=5, pady=5)

        ctk.CTkLabel(right_frame, text="Управление автоизменением", font=("Arial", 11, "bold")).pack(pady=5)

        # Статус
        self.auto_status_label = ctk.CTkLabel(
            right_frame,
            text="🔴 Остановлено",
            font=("Arial", 16, "bold"),
            text_color="red"
        )
        self.auto_status_label.pack(pady=10)

        # Кнопки управления
        control_frame = ctk.CTkFrame(right_frame)
        control_frame.pack(pady=20)

        self.start_auto_btn = ctk.CTkButton(
            control_frame,
            text="▶️ Запустить автоизменение",
            command=self.start_auto_price_changing,
            width=250,
            height=60,
            font=("Arial", 15, "bold"),
            fg_color="green",
            hover_color="darkgreen"
        )
        self.start_auto_btn.pack(pady=10)

        self.stop_auto_btn = ctk.CTkButton(
            control_frame,
            text="⏹️ Остановить автоизменение",
            command=self.stop_auto_price_changing,
            width=250,
            height=60,
            font=("Arial", 15, "bold"),
            fg_color="red",
            hover_color="darkred",
            state="disabled"
        )
        self.stop_auto_btn.pack(pady=10)

        # Лог автоизменений
        ctk.CTkLabel(right_frame, text="Лог событий:", font=("Arial", 11, "bold")).pack(pady=10)
        self.auto_log = ctk.CTkTextbox(right_frame, width=550, height=400, font=("Courier", 8))
        self.auto_log.pack(pady=10)

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

    def setup_offers_tab(self):
        """Вкладка офферов (ИСПРАВЛЕНО с поиском и прокруткой)"""
        main_container = ctk.CTkFrame(self.tab_offers)
        main_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Левая часть - таблица
        left_frame = ctk.CTkFrame(main_container)
        left_frame.pack(side="left", fill="both", expand=True, padx=5)

        ctk.CTkLabel(left_frame, text="Список офферов", font=("Arial", 11, "bold")).pack(pady=10)

        # ✅ ДОБАВЛЕНО: Поиск
        search_frame = ctk.CTkFrame(left_frame)
        search_frame.pack(pady=10, padx=10, fill="x")

        ctk.CTkLabel(search_frame, text="🔍 Поиск:", font=("Arial", 12)).pack(side="left", padx=5)

        self.search_var.trace("w", self.filter_offers)  # Фильтр при вводе

        search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var, width=250, height=30)
        search_entry.pack(side="left", padx=5)

        ctk.CTkButton(
            search_frame,
            text="❌ Очистить",
            command=lambda: self.search_var.set(""),
            width=100,
            height=35
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            left_frame,
            text="🔄 Обновить список",
            command=self.load_offers,
            width=200,
            height=40
        ).pack(pady=10)

        table_frame = ctk.CTkFrame(left_frame)
        table_frame.pack(fill="both", expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(table_frame)
        scrollbar.pack(side="right", fill="y")

        self.offers_tree = ttk.Treeview(
            table_frame,
            columns=("ID", "Game", "Price", "Stock", "Status"),
            show="headings",
            height=25,
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.offers_tree.yview)

        self.offers_tree.heading("ID", text="Offer ID")
        self.offers_tree.heading("Game", text="Игра")
        self.offers_tree.heading("Price", text="Цена")
        self.offers_tree.heading("Stock", text="Склад")
        self.offers_tree.heading("Status", text="Статус")

        self.offers_tree.column("ID", width=100)
        self.offers_tree.column("Game", width=350)
        self.offers_tree.column("Price", width=100)
        self.offers_tree.column("Stock", width=80)
        self.offers_tree.column("Status", width=100)

        self.offers_tree.pack(fill="both", expand=True)

        # Правая часть - управление с прокруткой
        right_frame = ctk.CTkFrame(main_container, width=450)
        right_frame.pack(side="right", fill="both", padx=5)

        ctk.CTkLabel(right_frame, text="Управление оффером", font=("Arial", 11, "bold")).pack(pady=5)

        # ✅ ИСПРАВЛЕНО: Добавлена прокрутка для кнопок
        scrollable_right = ctk.CTkScrollableFrame(right_frame, width=360, height=650)
        scrollable_right.pack(fill="both", expand=True, padx=5, pady=5)

        self.selected_offer_label = ctk.CTkLabel(
            scrollable_right,
            text="Выберите оффер из списка",
            font=("Arial", 12),
            wraplength=400,
            justify="left"
        )
        self.selected_offer_label.pack(pady=10)

        ctk.CTkLabel(scrollable_right, text="Точечные операции:", font=("Arial", 11, "bold")).pack(pady=10)

        ctk.CTkButton(
            scrollable_right,
            text="💰 Изменить цену",
            command=self.change_selected_offer_price,
            width=250,
            height=50
        ).pack(pady=8)

        ctk.CTkButton(
            scrollable_right,
            text="📦 Изменить количество",
            command=self.change_selected_offer_stock,
            width=250,
            height=50
        ).pack(pady=8)

        self.auto_toggle_btn = ctk.CTkButton(
            scrollable_right,
            text="🤖 Включить автоизменение",
            command=self.toggle_auto_for_offer,
            width=250,
            height=50,
            fg_color="#00CC00",  # ✅ По умолчанию зелёный (выключено)
            hover_color="#009900"
        )
        self.auto_toggle_btn.pack(pady=8)

        ctk.CTkButton(
            scrollable_right,
            text="✅ Активировать",
            command=self.activate_selected_offer,
            width=250,
            height=50
        ).pack(pady=8)

        ctk.CTkButton(
            scrollable_right,
            text="❌ Деактивировать",
            command=self.deactivate_selected_offer,
            width=250,
            height=50
        ).pack(pady=8)

        ctk.CTkButton(
            scrollable_right,
            text="🗑️ Удалить оффер",
            command=self.delete_selected_offer,
            width=250,
            height=50,
            fg_color="red",
            hover_color="darkred"
        ).pack(pady=8)

        ctk.CTkLabel(scrollable_right, text="─" * 35).pack(pady=5)

        ctk.CTkLabel(scrollable_right, text="Массовые операции:", font=("Arial", 11, "bold")).pack(pady=10)

        ctk.CTkButton(
            scrollable_right,
            text="📉 Снизить все цены на %",
            command=self.reduce_all_prices,
            width=250,
            height=50
        ).pack(pady=8)

        ctk.CTkButton(
            scrollable_right,
            text="🗑️ Удалить офферы по цене",
            command=self.remove_offers_by_price,
            width=250,
            height=50
        ).pack(pady=8)

        # ✅ ИСПРАВЛЕНО: Правильная привязка события
        self.offers_tree.bind("<<TreeviewSelect>>", self.on_offer_select)

    def filter_offers(self, *args):
        """Фильтрация офферов по поисковому запросу"""
        search_query = self.search_var.get().lower()
            # Очищаем таблицу
        for item in self.offers_tree.get_children():
            self.offers_tree.delete(item)
        # Если поиск пустой - показываем все
        if not search_query:
            for product_id, info in self.offers_data.items():
                self.offers_tree.insert("", "end", values=(
                    info.get("id", "N/A"),
                    info.get("product_name", "N/A"),
                    f"€{info.get('price', 0)}",
                    info.get("current_stock", 0),
                    "Активен" if info.get("is_active") else "Неактивен"
                ))
            return

            # Фильтруем по названию игры
        for product_id, info in self.offers_data.items():
            game_name = info.get("product_name", "").lower()

            if search_query in game_name:
                self.offers_tree.insert("", "end", values=(
                    info.get("id", "N/A"),
                    info.get("product_name", "N/A"),
                    f"€{info.get('price', 0)}",
                    info.get("current_stock", 0),
                    "Активен" if info.get("is_active") else "Неактивен"
                ))

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
        # Загружаем из g2a_config (который уже читает JSON)
        self.client_id_var.set(g2a_config.G2A_CLIENT_ID)
        self.client_secret_var.set(g2a_config.G2A_CLIENT_SECRET)
        self.client_email_var.set(g2a_config.G2A_CLIENT_EMAIL)
        self.telegram_token_var.set(g2a_config.TELEGRAM_BOT_TOKEN)
        self.telegram_chat_var.set(g2a_config.TELEGRAM_CHAT_ID)

        # Загружаем настройки автоизменения
        self.load_auto_settings()

        print("✅ Настройки загружены из g2a_config")

    def load_auto_settings(self):
        """Загрузка настроек автоизменения"""
        try:
            from auto_price_changer import AutoPriceSettings
            settings_obj = AutoPriceSettings()
            s = settings_obj.settings

            self.auto_enabled_var.set(s.get("enabled", False))
            self.auto_telegram_var.set(s.get("telegram_notifications", False))
            self.auto_interval_var.set(s.get("check_interval", 1800))
            self.auto_undercut_var.set(s.get("undercut_amount", 0.01))
            self.auto_min_price_var.set(s.get("min_price", 0.1))
            self.auto_max_price_var.set(s.get("max_price", 100.0))
            self.auto_daily_limit_var.set(s.get("daily_limit", 20))

        except Exception as e:
            print(f"Ошибка загрузки настроек авто: {e}")

    def save_all_settings(self):
        """Сохранение всех настроек (ИСПРАВЛЕНО)"""
        # Получаем данные из полей GUI
        client_id = self.client_id_var.get().strip()
        client_secret = self.client_secret_var.get().strip()
        client_email = self.client_email_var.get().strip()
        telegram_token = self.telegram_token_var.get().strip()
        telegram_chat = self.telegram_chat_var.get().strip()

        # Проверка обязательных полей
        if not client_id or not client_secret or not client_email:
            messagebox.showerror(
                "Ошибка",
                "Заполните все обязательные поля G2A:\n\n"
                "• G2A Client ID\n"
                "• G2A Client Secret\n"
                "• G2A Account Email"
            )
            return

        # Сохраняем в JSON файл
        config_data = {
            "G2A_CLIENT_ID": client_id,
            "G2A_CLIENT_SECRET": client_secret,
            "G2A_CLIENT_EMAIL": client_email,
            "TELEGRAM_BOT_TOKEN": telegram_token,
            "TELEGRAM_CHAT_ID": telegram_chat,
            "TELEGRAM_ENABLED": self.telegram_enabled.get()
        }

        try:
            with open("g2a_config_saved.json", "w", encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)

            print("✅ Настройки сохранены в g2a_config_saved.json")

            # ✅ ИСПРАВЛЕНИЕ: Перезагружаем g2a_config
            g2a_config.reload_config()

            # ✅ ИСПРАВЛЕНИЕ: Обновляем глобальный notifier в telegram_notifier
            if telegram_token and telegram_chat:
                from telegram_notifier import notifier
                notifier.update_credentials(telegram_token, telegram_chat)
                print(f"✅ Telegram notifier обновлен | Chat ID: {telegram_chat}")
            else:
                print("⚠️ Telegram не настроен (токен или chat_id пусты)")

            messagebox.showinfo(
                "Успех",
                "✅ Настройки сохранены и применены!\n\n"
                "Данные будут использоваться при следующих запросах к G2A API."
            )

        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")
            messagebox.showerror("Ошибка", f"Не удалось сохранить настройки:\n{e}")

    def save_auto_settings(self):
        """Сохранение настроек автоизменения"""
        try:
            from auto_price_changer import AutoPriceSettings
            settings_obj = AutoPriceSettings()
            settings_obj.settings.update({
                "enabled": self.auto_enabled_var.get(),
                "telegram_notifications": self.auto_telegram_var.get(),
                "check_interval": self.auto_interval_var.get(),
                "undercut_amount": self.auto_undercut_var.get(),
                "min_price": self.auto_min_price_var.get(),
                "max_price": self.auto_max_price_var.get(),
                "daily_limit": self.auto_daily_limit_var.get()
            })
            settings_obj.save_settings()
            messagebox.showinfo("Успех", "✅ Настройки автоизменения сохранены!")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить: {e}")

    def start_auto_price_changing(self):
        """Запуск автоизменения цен (ИСПРАВЛЕНО)"""
        if self.auto_running:
            messagebox.showwarning("Внимание", "Автоизменение уже запущено!")
            return

        if not self.auto_enabled_var.get():
            messagebox.showwarning("Внимание", "Сначала включите автоизменение в настройках и сохраните!")
            return

        # Проверяем настройки G2A API
        g2a_config.reload_config()
        if not g2a_config.G2A_CLIENT_ID or not g2a_config.G2A_CLIENT_SECRET:
            messagebox.showerror(
                "Ошибка",
                "Не заполнены данные G2A API!\n\n"
                "Перейдите в 'Настройки' и заполните:\n"
                "• G2A Client ID\n"
                "• G2A Client Secret\n"
                "• G2A Email"
            )
            return

        def run_auto():
            import auto_price_changer
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            self.auto_running = True
            self.auto_status_label.configure(text="🟢 Работает", text_color="green")
            self.start_auto_btn.configure(state="disabled")
            self.stop_auto_btn.configure(state="normal")

            self.auto_log_message("✅ Автоизменение запущено")
            self.auto_log_message(f"📋 Интервал: {self.auto_interval_var.get()}с")
            self.auto_log_message(f"📊 Дневной лимит: {self.auto_daily_limit_var.get()}")

            try:
                # ✅ ИСПРАВЛЕНИЕ: Сохраняем ссылку на объект changer
                self.auto_changer = auto_price_changer.AutoPriceChanger()

                # Перенаправляем вывод в GUI
                import sys
                from io import StringIO

                class GUILogger:
                    def __init__(self, gui_callback):
                        self.gui_callback = gui_callback

                    def write(self, message):
                        if message.strip():
                            self.gui_callback(message.strip())

                    def flush(self):
                        pass

                # Сохраняем оригинальный stdout
                original_stdout = sys.stdout

                # Устанавливаем наш логгер
                gui_logger = GUILogger(self.auto_log_message)
                sys.stdout = gui_logger

                # Запускаем автоизменение
                loop.run_until_complete(self.auto_changer.start())

                # Восстанавливаем stdout
                sys.stdout = original_stdout

            except Exception as e:
                self.auto_log_message(f"❌ Ошибка: {e}")
                import traceback
                self.auto_log_message(traceback.format_exc())
            finally:
                self.auto_running = False
                self.auto_changer = None  # ✅ Очищаем ссылку
                self.auto_status_label.configure(text="🔴 Остановлено", text_color="red")
                self.start_auto_btn.configure(state="normal")
                self.stop_auto_btn.configure(state="disabled")
                loop.close()

        self.auto_process = threading.Thread(target=run_auto, daemon=True)
        self.auto_process.start()

    def stop_auto_price_changing(self):
        """Остановка автоизменения (ИСПРАВЛЕНО)"""
        if not self.auto_running:
            messagebox.showinfo("Инфо", "Автоизменение не запущено")
            return

        # ✅ ИСПРАВЛЕНИЕ: Останавливаем через объект
        if hasattr(self, 'auto_changer') and self.auto_changer:
            self.auto_changer.stop()
            self.auto_log_message("🛑 Остановка автоизменения...")
            self.stop_auto_btn.configure(state="disabled")
            messagebox.showinfo("Инфо", "Автоизменение остановлено")
        else:
            self.auto_running = False
            self.auto_log_message("🛑 Принудительная остановка...")
            messagebox.showinfo("Инфо", "Автоизменение будет остановлено")

    def auto_log_message(self, msg):
        """Добавить сообщение в лог автоизменения"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.auto_log.insert("end", f"[{timestamp}] {msg}\n")
        self.auto_log.see("end")

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

    def load_offers(self):
        """Загрузка офферов"""

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                self.api_client = G2AApiClient()

                print("Получение токена G2A...")
                loop.run_until_complete(self.api_client.get_token())
                print("✅ Токен получен")

                print("Загрузка офферов...")
                result = loop.run_until_complete(self.api_client.get_offers())

                if result.get("success"):
                    # Очищаем таблицу
                    for item in self.offers_tree.get_children():
                        self.offers_tree.delete(item)

                    self.offers_data = result.get("offers_cache", {})

                    for product_id, info in self.offers_data.items():
                        self.offers_tree.insert("", "end", values=(
                            info.get("id", "N/A"),
                            info.get("product_name", "N/A"),
                            f"€{info.get('price', 0)}",
                            info.get("current_stock", 0),
                            "Активен" if info.get("is_active") else "Неактивен"
                        ))

                    print(f"✅ Загружено {len(self.offers_data)} офферов")
                    messagebox.showinfo("Готово", f"Загружено {len(self.offers_data)} офферов")
                else:
                    error_msg = result.get("error", "Неизвестная ошибка")
                    print(f"❌ Ошибка: {error_msg}")
                    messagebox.showerror("Ошибка", f"Не удалось загрузить офферы:\n{error_msg}")

            except Exception as e:
                print(f"❌ Исключение: {e}")
                import traceback
                traceback.print_exc()
                messagebox.showerror("Ошибка", f"Ошибка загрузки офферов:\n{str(e)}")
            finally:
                loop.close()

        threading.Thread(target=run, daemon=True).start()

    def on_offer_select(self, event):
        """Выбор оффера (ПОЛНОСТЬЮ ПЕРЕРАБОТАНО)"""
        selection = self.offers_tree.selection()
        if not selection:
            return

        item = self.offers_tree.item(selection[0])
        values = item['values']

        if len(values) >= 5:
            offer_id = values[0]

            # Находим product_id
            product_id = None
            for pid, info in self.offers_data.items():
                if info.get("id") == offer_id:
                    product_id = pid
                    break

            # ✅ НОВАЯ ЛОГИКА: Простая проверка
            auto_status = "🔴 ВЫКЛЮЧЕНО"
            is_allowed = False

            try:
                from auto_price_changer import AutoPriceSettings
                settings = AutoPriceSettings()

                if product_id:
                    global_enabled = settings.settings.get("enabled", False)
                    excluded = settings.settings.get("excluded_products", [])
                    included = settings.settings.get("included_products", [])

                    # Проверяем по новой логике
                    if not global_enabled:
                        auto_status = "🔴 ВЫКЛЮЧЕНО (глобально)"
                        is_allowed = False
                    elif str(product_id) in excluded:
                        auto_status = "🔴 ВЫКЛЮЧЕНО (исключение)"
                        is_allowed = False
                    elif included:  # Есть белый список
                        if str(product_id) in included:
                            auto_status = "🟢 ВКЛЮЧЕНО (точечно)"
                            is_allowed = True
                        else:
                            auto_status = "🔴 ВЫКЛЮЧЕНО (не в белом списке)"
                            is_allowed = False
                    else:  # Нет белого списка, глобально включено
                        auto_status = "🟢 ВКЛЮЧЕНО (глобально)"
                        is_allowed = True

                    # Обновляем кнопку
                    self.update_auto_toggle_button_state(is_allowed)

            except Exception as e:
                print(f"Ошибка проверки автоизменения: {e}")
                import traceback
                traceback.print_exc()
                auto_status = "❌ Ошибка проверки"

            offer_id_short = str(values[0])[:8] + "..." if len(str(values[0])) > 12 else str(values[0])

            info_text = f"""
📋 Оффер: {offer_id_short}

🎮 Игра:
{values[1]}

💰 Цена: {values[2]}
📦 Склад: {values[3]}
✅ Статус: {values[4]}

🤖 Автоизменение:
{auto_status}
"""

            self.selected_offer_label.configure(text=info_text)

    def get_selected_offer(self):
        """Получить выбранный оффер"""
        selection = self.offers_tree.selection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите оффер")
            return None

        item = self.offers_tree.item(selection[0])
        values = item['values']

        if len(values) >= 5:
            offer_id = values[0]
            for product_id, info in self.offers_data.items():
                if info.get("id") == offer_id:
                    return {
                        "offer_id": offer_id,
                        "product_id": product_id,
                        "game_name": values[1],
                        "price": float(values[2].replace("€", "")),
                        "stock": int(values[3]),
                        "is_active": values[4] == "Активен",
                        "offer_type": info.get("offer_type", "dropshipping")
                    }
        return None

    def change_selected_offer_price(self):
        """Изменить цену выбранного оффера (ИСПРАВЛЕНО - Event Loop)"""
        offer = self.get_selected_offer()
        if not offer:
            return

        new_price = simpledialog.askfloat(
            "Изменение цены",
            f"Текущая цена: €{offer['price']:.2f}\n\nВведите новую цену (EUR):",
            minvalue=0.01,
            maxvalue=1000.0
        )

        if new_price is None:
            return

        def run():
            # ✅ ИСПРАВЛЕНИЕ: Создаём НОВЫЙ event loop для каждого запроса
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Создаём НОВЫЙ клиент для этого запроса
                api_client = G2AApiClient()

                async def update_price():
                    # Получаем токен
                    await api_client.get_token()

                    # Получаем детали оффера
                    details = await api_client.get_offer_details(offer['offer_id'])

                    if not details.get("success"):
                        raise Exception("Не удалось получить детали оффера")

                    offer_data = details.get("data", {})

                    # Формируем данные для обновления
                    update_data = {
                        "offerType": offer.get('offer_type', 'dropshipping'),
                        "variant": {
                            "price": {
                                "retail": str(new_price),
                                "business": str(new_price)
                            },
                            "active": True,
                            "visibility": offer_data.get("visibility", "all")
                        }
                    }

                    # Добавляем regions если есть
                    if "regions" in offer_data:
                        update_data["variant"]["regions"] = offer_data["regions"]

                    if "regionRestrictions" in offer_data:
                        update_data["variant"]["regionRestrictions"] = offer_data["regionRestrictions"]

                    # Обновляем
                    result = await api_client.update_offer_partial(offer['offer_id'], update_data)

                    return result

                # Запускаем асинхронную функцию
                result = loop.run_until_complete(update_price())

                if result.get("success"):
                    messagebox.showinfo("Успех", f"✅ Цена обновлена на €{new_price:.2f}")
                    # Обновляем список офферов в главном потоке
                    self.after(100, self.load_offers)
                else:
                    messagebox.showerror("Ошибка", f"Не удалось обновить цену:\n{result.get('error')}")

            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка обновления цены:\n{str(e)}")
            finally:
                # ✅ ВАЖНО: Закрываем loop ПОСЛЕ завершения всех операций
                try:
                    # Отменяем все pending tasks
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()

                    # Даём время на завершение
                    loop.run_until_complete(asyncio.sleep(0.1))
                except:
                    pass
                finally:
                    loop.close()

        threading.Thread(target=run, daemon=True).start()

    def change_selected_offer_stock(self):
        """Изменить stock (ИСПРАВЛЕНО)"""
        offer = self.get_selected_offer()
        if not offer:
            return

        new_stock = simpledialog.askinteger(
            "Изменение количества",
            f"Текущий stock: {offer['stock']}\n\nВведите новое количество:",
            minvalue=0,
            maxvalue=10000
        )

        if new_stock is None:
            return

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                api_client = G2AApiClient()

                async def update_stock():
                    await api_client.get_token()

                    update_data = {
                        "offerType": offer.get('offer_type', 'dropshipping'),
                        "variant": {
                            "inventory": {
                                "size": new_stock
                            }
                        }
                    }

                    result = await api_client.update_offer_partial(offer['offer_id'], update_data)
                    return result

                result = loop.run_until_complete(update_stock())

                if result.get("success"):
                    messagebox.showinfo("Успех", f"✅ Stock обновлен: {new_stock}")
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

    def activate_selected_offer(self):
        """Активировать оффер"""
        offer = self.get_selected_offer()
        if not offer:
            return

        if offer['is_active']:
            messagebox.showinfo("Инфо", "Оффер уже активен")
            return

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if not self.api_client:
                    self.api_client = G2AApiClient()
                    loop.run_until_complete(self.api_client.get_token())

                update_data = {
                    "offerType": offer.get('offer_type', 'dropshipping'),
                    "variant": {
                        "active": True
                    }
                }

                result = loop.run_until_complete(
                    self.api_client.update_offer_partial(offer['offer_id'], update_data)
                )

                if result.get("success"):
                    messagebox.showinfo("Успех", "✅ Оффер активирован")
                    self.load_offers()
                else:
                    messagebox.showerror("Ошибка", result.get("error"))

            except Exception as e:
                messagebox.showerror("Ошибка", str(e))
            finally:
                loop.close()

        threading.Thread(target=run, daemon=True).start()

    def deactivate_selected_offer(self):
        """Деактивировать оффер"""
        offer = self.get_selected_offer()
        if not offer:
            return

        if not offer['is_active']:
            messagebox.showinfo("Инфо", "Оффер уже неактивен")
            return

        confirm = messagebox.askyesno("Подтверждение", f"Деактивировать {offer['game_name']}?")
        if not confirm:
            return

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if not self.api_client:
                    self.api_client = G2AApiClient()
                    loop.run_until_complete(self.api_client.get_token())

                update_data = {
                    "offerType": offer.get('offer_type', 'dropshipping'),
                    "variant": {
                        "active": False
                    }
                }

                result = loop.run_until_complete(
                    self.api_client.update_offer_partial(offer['offer_id'], update_data)
                )

                if result.get("success"):
                    messagebox.showinfo("Успех", "✅ Оффер деактивирован")
                    self.load_offers()
                else:
                    messagebox.showerror("Ошибка", result.get("error"))

            except Exception as e:
                messagebox.showerror("Ошибка", str(e))
            finally:
                loop.close()

        threading.Thread(target=run, daemon=True).start()

    def delete_selected_offer(self):
        """Удалить оффер"""
        offer = self.get_selected_offer()
        if not offer:
            return

        confirm = messagebox.askyesno(
            "⚠️ УДАЛЕНИЕ",
            f"УДАЛИТЬ {offer['game_name']}?\n\nЭто действие нельзя отменить!",
            icon='warning'
        )

        if not confirm:
            return

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if not self.api_client:
                    self.api_client = G2AApiClient()
                    loop.run_until_complete(self.api_client.get_token())

                # Сначала деактивируем
                deactivate_data = {
                    "offerType": offer.get('offer_type', 'dropshipping'),
                    "variant": {
                        "active": False
                    }
                }

                loop.run_until_complete(
                    self.api_client.update_offer_partial(offer['offer_id'], deactivate_data)
                )

                # Затем удаляем
                result = loop.run_until_complete(
                    self.api_client.delete_offer(offer['offer_id'])
                )

                if result.get("success"):
                    messagebox.showinfo("Успех", "✅ Оффер удален")
                    self.load_offers()
                else:
                    messagebox.showerror("Ошибка", result.get("error"))

            except Exception as e:
                messagebox.showerror("Ошибка", str(e))
            finally:
                loop.close()

        threading.Thread(target=run, daemon=True).start()

    def reduce_all_prices(self):
        """Массовое снижение (ИСПРАВЛЕНО)"""

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Перезагружаем конфиг перед операцией
                g2a_config.reload_config()

                loop.run_until_complete(self.price_parser.reduce_all_prices_by_percentage())
                messagebox.showinfo("Готово", "✅ Цены снижены!")
                self.load_offers()
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))
            finally:
                loop.close()

        threading.Thread(target=run, daemon=True).start()

    def remove_offers_by_price(self):
        """Удаление по цене"""

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.price_parser.remove_offers_by_price())
                messagebox.showinfo("Готово", "✅ Офферы удалены!")
                self.load_offers()
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))
            finally:
                loop.close()

        threading.Thread(target=run, daemon=True).start()

    def toggle_auto_for_offer(self):
        """Включить/выключить автоизменение для выбранного оффера (ИСПРАВЛЕНО)"""
        offer = self.get_selected_offer()
        if not offer:
            return

        product_id = offer['product_id']
        game_name = offer['game_name']

        try:
            from auto_price_changer import AutoPriceSettings
            settings = AutoPriceSettings()

            # ✅ НОВАЯ ПРОВЕРКА: используем is_product_allowed
            is_currently_enabled = settings.is_product_allowed(product_id)

            if is_currently_enabled:
                # Сейчас ВКЛЮЧЕНО → выключаем
                confirm = messagebox.askyesno(
                    "Отключение автоизменения",
                    f"Отключить автоизменение цены для:\n\n{game_name}\n\nЦена НЕ будет меняться автоматически."
                )

                if confirm:
                    settings.toggle_product(product_id, enabled=False)
                    messagebox.showinfo("Успех", f"✅ Автоизменение ОТКЛЮЧЕНО для:\n{game_name}")
                    self.refresh_selected_offer_info()
            else:
                # Сейчас ВЫКЛЮЧЕНО → включаем

                # ✅ ПРОВЕРКА: если глобально выключено - сначала включаем глобально
                if not settings.settings.get("enabled", False):
                    msg = (
                        f"Автоизменение глобально ВЫКЛЮЧЕНО!\n\n"
                        f"Чтобы включить автоизменение для '{game_name}',\n"
                        f"сначала нужно включить его глобально во вкладке 'Автоизменение'.\n\n"
                        f"Включить глобально СЕЙЧАС?"
                    )

                    if messagebox.askyesno("Включить глобально?", msg):
                        settings.settings["enabled"] = True
                        settings.save_settings()
                        # Обновляем GUI ползунок
                        self.auto_enabled_var.set(True)
                        print("✅ Глобальное автоизменение ВКЛЮЧЕНО")

                confirm = messagebox.askyesno(
                    "Включение автоизменения",
                    f"Включить автоизменение цены для:\n\n{game_name}\n\nЦена будет меняться автоматически на основе конкурентов."
                )

                if confirm:
                    settings.toggle_product(product_id, enabled=True)
                    messagebox.showinfo("Успех", f"✅ Автоизменение ВКЛЮЧЕНО для:\n{game_name}")
                    self.refresh_selected_offer_info()

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось изменить настройки: {e}")
            import traceback
            traceback.print_exc()

    def refresh_selected_offer_info(self):
        """Обновление информации о выбранном оффере"""
        # Просто вызываем on_offer_select с пустым event
        selection = self.offers_tree.selection()
        if selection:
            self.on_offer_select(None)

        item = self.offers_tree.item(selection[0])
        values = item['values']

        if len(values) >= 5:
            offer_id = values[0]

            # Находим product_id
            product_id = None
            for pid, info in self.offers_data.items():
                if info.get("id") == offer_id:
                    product_id = pid
                    break

            # Проверяем статус автоизменения
            auto_status = "🔴 ВЫКЛЮЧЕНО (по умолчанию)"
            is_allowed = False

            try:
                from auto_price_changer import AutoPriceSettings
                settings = AutoPriceSettings()

                if product_id:
                    excluded = settings.settings.get("excluded_products", [])
                    included = settings.settings.get("included_products", [])

                    # Если в чёрном списке - точно выключено
                    if str(product_id) in excluded:
                        auto_status = "🔴 ВЫКЛЮЧЕНО"
                        is_allowed = False
                    # Если есть белый список - проверяем его
                    elif included:
                        if str(product_id) in included:
                            auto_status = "🟢 ВКЛЮЧЕНО"
                            is_allowed = True
                        else:
                            auto_status = "🔴 ВЫКЛЮЧЕНО"
                            is_allowed = False
                    # Если нет белого списка - проверяем глобальную настройку
                    else:
                        global_enabled = settings.settings.get("enabled", False)

                        # ✅ ИСПРАВЛЕНИЕ: Если глобально выключено - всё выключено
                        if not global_enabled:
                            auto_status = "🔴 ВЫКЛЮЧЕНО (глобально)"
                            is_allowed = False
                        else:
                            # Глобально включено, но нет белого списка - включено для всех
                            auto_status = "🟢 ВКЛЮЧЕНО (глобально)"
                            is_allowed = True

                    # Обновляем кнопку
                    self.update_auto_toggle_button_state(is_allowed)

            except Exception as e:
                print(f"Ошибка проверки автоизменения: {e}")
                auto_status = "❌ Ошибка проверки"

            info_text = f"""
📋 Выбранный оффер:

ID: {values[0]}
Игра: {values[1]}
Цена: {values[2]}
На складе: {values[3]}
Статус: {values[4]}

🤖 Автоизменение цены: {auto_status}
"""

            self.selected_offer_label.configure(text=info_text)

    def update_auto_toggle_button_state(self, is_enabled):
        """Обновление состояния кнопки автоизменения"""
        try:
            if is_enabled:
                # Автоизменение ВКЛЮЧЕНО
                self.auto_toggle_btn.configure(
                    text="🤖 Отключить автоизменение",
                    fg_color="#FF0000",  # Красный
                    hover_color="#CC0000"
                )
            else:
                # Автоизменение ВЫКЛЮЧЕНО
                self.auto_toggle_btn.configure(
                    text="🤖 Включить автоизменение",
                    fg_color="#00CC00",  # Зелёный
                    hover_color="#009900"
                )
        except Exception as e:
            print(f"Ошибка обновления кнопки: {e}")

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
        """Статистика цен (ИСПРАВЛЕНО - работает!)"""

        def load_stats():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                self.stats_text.delete("1.0", "end")
                self.stats_text.insert("1.0", f"⏳ Загрузка статистики за {period}...\n\n")

                # Импортируем конфиг
                from g2a_config import API_BASE_URL, ADMIN_API_KEY

                # Создаём HTTP клиент
                import httpx

                async def fetch_stats():
                    async with httpx.AsyncClient(verify=False) as client:
                        response = await client.get(
                            f"{API_BASE_URL}/admin/price-stats",
                            params={"period": period},
                            headers={'X-API-Key': ADMIN_API_KEY},
                            timeout=30.0
                        )

                        if response.status_code == 200:
                            return response.json()
                        else:
                            raise Exception(f"HTTP {response.status_code}: {response.text}")

                # Получаем данные
                data = loop.run_until_complete(fetch_stats())

                # Форматируем вывод
                self.stats_text.delete("1.0", "end")

                output = f"""
    ╔════════════════════════════════════════════════════════╗
    ║  📊 СТАТИСТИКА ИЗМЕНЕНИЙ ЦЕН - {data['period']}
    ╚════════════════════════════════════════════════════════╝

    📈 ОБЩАЯ СВОДКА:
    ───────────────────────────────────────────────────────────
        Всего изменений цен:     {data['summary']['total_changes']}
        📉 Понижений цен:         {data['summary']['price_decreases']}
        📈 Повышений цен:         {data['summary']['price_increases']}
        💰 Среднее изменение:     €{data['summary']['avg_price_change']:.2f}
        💸 Общее изменение:       €{data['summary']['total_price_change']:.2f}
      🕐 Изменений сегодня:     {data['summary']['today_changes']}

    """

                if data.get('top_changed_games'):
                    output += """
    ╔════════════════════════════════════════════════════════╗
    ║  🎮 ТОП-20 ИГР С НАИБОЛЬШИМИ ИЗМЕНЕНИЯМИ
    ╚════════════════════════════════════════════════════════╝

    """
                    for idx, game in enumerate(data['top_changed_games'], 1):
                        output += f"""
    {idx}. {game['game_name']}
        Изменений: {game['change_count']}
        Мин. старая цена: €{game['min_old_price']:.2f}
        Макс. новая цена: €{game['max_new_price']:.2f}
        Среднее изменение: €{game['avg_change']:.2f}
    """

                if data.get('recent_changes'):
                    output += """
    ╔════════════════════════════════════════════════════════╗
    ║  🕐 ПОСЛЕДНИЕ ИЗМЕНЕНИЯ (до 50)
    ╚════════════════════════════════════════════════════════╝

    """
                    for change in data['recent_changes'][:50]:
                        direction = "📉" if change['change_amount'] < 0 else "📈"
                        output += f"""
    {change['created_at']}
        {direction} {change['game_name']} (ID: {change['product_id']})
        Старая: €{change['old_price']:.2f} → Новая: €{change['new_price']:.2f}
        Рыночная: €{change['market_price']:.2f}
        Изменение: €{change['change_amount']:.2f}
        Причина: {change['change_reason']}
    ───────────────────────────────────────────────────────────
    """

                    if len(data['recent_changes']) > 50:
                        output += f"\n... и еще {len(data['recent_changes']) - 50} изменений\n"

                self.stats_text.insert("1.0", output)

            except Exception as e:
                self.stats_text.delete("1.0", "end")
                error_msg = f"""
    ❌ ОШИБКА ЗАГРУЗКИ СТАТИСТИКИ

    Ошибка: {str(e)}

    Возможные причины:
    1. API сервер не запущен
    2. Неверный API ключ
    3. Нет данных за выбранный период

    Проверьте:
    • Запущен ли g2a_fastapi_server.py
    • Правильность API_BASE_URL в g2a_config.py
    • Наличие изменений цен в базе данных
    """
                self.stats_text.insert("1.0", error_msg)

            finally:
                loop.close()

        # Запускаем в отдельном потоке
        threading.Thread(target=load_stats, daemon=True).start()

def main():
    app = G2AAutomationGUI()
    app.mainloop()


if __name__ == "__main__":
    main()