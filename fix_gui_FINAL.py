#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ GUI - уменьшение ВСЕХ элементов

import re

def fix_gui():
    try:
        with open('g2a_gui.py', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("❌ Файл g2a_gui.py не найден!")
        return False

    # Создаём бэкап
    with open('g2a_gui.py.backup', 'w', encoding='utf-8') as f:
        f.write(content)
    print("💾 Создан бэкап: g2a_gui.py.backup")

    original_content = content

    # ============================================================
    # ТОЧНЫЕ ЗАМЕНЫ РАЗМЕРОВ КНОПОК И ЭЛЕМЕНТОВ
    # ============================================================

    replacements = [
        # 1. Размер Tabview (уже изменён, но на всякий случай)
        ('width=1100, height=750', 'width=1050, height=700'),

        # 2. НАСТРОЙКИ - ScrollableFrame
        ('width=600, height=650', 'width=550, height=600'),

        # 3. НАСТРОЙКИ - Entry поля
        ('width=500, height=30', 'width=450, height=28'),

        # 4. НАСТРОЙКИ - Кнопка сохранения
        ('width=300,\n                height=50,\n                font=("Arial", 16, "bold")',
         'width=240, height=42, font=("Arial", 14, "bold")'),

        # 5. АВТОИЗМЕНЕНИЕ - ScrollableFrame
        ('width=380, height=600', 'width=340, height=560'),

        # 6. АВТОИЗМЕНЕНИЕ - Кнопка сохранения
        ('width=180,\n                height=45,\n                font=("Arial", 13, "bold")',
         'width=150, height=38, font=("Arial", 12, "bold")'),

        # 7. АВТОИЗМЕНЕНИЕ - Управление (большие кнопки)
        ('width=250,\n                height=60,\n                font=("Arial", 15, "bold")',
         'width=200, height=50, font=("Arial", 14, "bold")'),

        # 8. АВТОИЗМЕНЕНИЕ - Лог
        ('width=650, height=450', 'width=550, height=400'),

        # 9. ПАРСИНГ - Заголовок
        ('pady=20\n        btnframe', 'pady=10\n        btnframe'),

        # 10. ПАРСИНГ - Кнопки (280x70)
        ('width=280,\n                height=70,\n                font=("Arial", 15)',
         'width=220, height=55, font=("Arial", 13)'),

        # 11. ПАРСИНГ - Progress bar
        ('width=600, height=20', 'width=550, height=18'),

        # 12. ПАРСИНГ - Log text
        ('width=750, height=450, font=("Courier", 10)',
         'width=650, height=400, font=("Courier", 9)'),

        # 13. ОФФЕРЫ - Поиск Entry
        ('width=300, height=35', 'width=250, height=30'),

        # 14. ОФФЕРЫ - Кнопка очистить
        ('width=100,\n                height=35',
         'width=80, height=30'),

        # 15. ОФФЕРЫ - Кнопка обновить
        ('width=200,\n                height=40',
         'width=160, height=35'),

        # 16. ОФФЕРЫ - ScrollableFrame правой панели
        ('width=420, height=750', 'width=360, height=650'),

        # 17. ОФФЕРЫ - Все кнопки управления (250x50)
        ('width=250,\n                height=50',
         'width=200, height=42'),

        # 18. КЛЮЧИ - Кнопки
        ('width=250,\n                height=60',
         'width=200, height=48'),

        # 19. КЛЮЧИ - Stats scrollable
        ('width=900, height=600', 'width=750, height=520'),

        # 20. СТАТИСТИКА - Кнопки периодов
        ('width=160,\n                height=45',
         'width=130, height=38'),

        # 21. СТАТИСТИКА - Textbox
        ('width=800, height=550, font=("Courier", 10)',
         'width=700, height=480, font=("Courier", 9)'),

        # 22. Уменьшение отступов pady
        ('pady=20\n    ', 'pady=12\n    '),
        ('pady=15\n    ', 'pady=10\n    '),
    ]

    # Применяем замены
    changes_count = 0
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            changes_count += 1

    # Сохраняем
    with open('g2a_gui.py', 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\n✅ Применено {changes_count} изменений")
    print()
    print("📊 ЧТО ИЗМЕНЕНО:")
    print("  • Tabview: 1100x750 → 1050x700")
    print("  • Все ScrollableFrame уменьшены на 50-60px")
    print("  • Все Entry поля: на 50px меньше")
    print("  • Все кнопки: уменьшены на 20-30%")
    print("  • Все отступы (pady): уменьшены")
    print()
    print("🎯 РЕЗУЛЬТАТ:")
    print("  Все элементы должны поместиться в окно 1200x800!")

    return True

if __name__ == "__main__":
    print("=" * 70)
    print("  ФИНАЛЬНОЕ УМЕНЬШЕНИЕ ВСЕХ ЭЛЕМЕНТОВ GUI")
    print("=" * 70)
    print()

    if fix_gui():
        print()
        print("=" * 70)
        print("✅ ГОТОВО! Перезапустите GUI: python g2a_gui.py")
        print("=" * 70)
    else:
        print()
        print("❌ ОШИБКА!")

    input("\nНажмите Enter для выхода...")
