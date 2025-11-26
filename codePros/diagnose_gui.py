#!/usr/bin/env python
# diagnose_gui.py - Диагностика проблем с GUI

import os
import sys
import traceback
import time

print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                    🔍 ДИАГНОСТИКА G2A_AUTOMATION 🔍                      ║
╚════════════════════════════════════════════════════════════════════════════╝
""")

print("\n📋 ШАГ 1: ПРОВЕРКА ФАЙЛОВ")
print("=" * 80)

required_files = [
    'g2a_gui.py',
    'g2a_config.py',
    'g2a_api_client.py',
    'key_manager.py',
    'price_parser.py',
    'database.py',
    'telegram_notifier.py',
]

for file_name in required_files:
    if os.path.exists(file_name):
        size = os.path.getsize(file_name)
        print(f"✅ {file_name} - OK ({size} bytes)")
    else:
        print(f"❌ {file_name} - НЕ НАЙДЕН!")

print("\n🔍 ШАГ 2: ПРОВЕРКА ИМПОРТОВ")
print("=" * 80)

imports_to_test = [
    'customtkinter',
    'tkinter',
    'asyncio',
    'httpx',
    'requests',
    'json',
    'os',
]

for module_name in imports_to_test:
    try:
        __import__(module_name)
        print(f"✅ {module_name} - OK")
    except ImportError as e:
        print(f"❌ {module_name} - ОШИБКА: {e}")
    except Exception as e:
        print(f"⚠️  {module_name} - ОШИБКА: {e}")

print("\n🚀 ШАГ 3: ЗАГРУЗКА g2a_gui")
print("=" * 80)

try:
    print("⏳ Загружаю g2a_gui.py...")
    from g2a_gui import G2AAutomationGUI

    print("✅ g2a_gui загружен успешно!")

    print("\n⏳ Создаю окно GUI...")
    app = G2AAutomationGUI()

    print("✅ Окно создано!")

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
    print("\n🚀 Запускаю GUI (нажми Alt+F4 чтобы закрыть)...")
    print("=" * 80)

    app.mainloop()

    print("\n✅ GUI завершил работу нормально")

except ImportError as e:
    print(f"\n❌ ОШИБКА ИМПОРТА:")
    print(f"   {e}")
    print("\n📋 ПОЛНАЯ ТРАССИРОВКА:")
    traceback.print_exc()
    print("\n💡 РЕШЕНИЕ:")
    print("   Убедись что все модули установлены: pip install customtkinter httpx asyncio")

except ModuleNotFoundError as e:
    print(f"\n❌ МОДУЛЬ НЕ НАЙДЕН:")
    print(f"   {e}")
    print("\n📋 ПОЛНАЯ ТРАССИРОВКА:")
    traceback.print_exc()
    print("\n💡 РЕШЕНИЕ:")
    print("   Установи недостающий модуль: pip install {e.name}")

except Exception as e:
    print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА:")
    print(f"   {e}")
    print("\n📋 ПОЛНАЯ ТРАССИРОВКА:")
    traceback.print_exc()
    print("\n💡 РЕШЕНИЕ:")
    print("   Скопируй эту ошибку и отправь разработчику")

finally:
    print("\n" + "=" * 80)
    print("⏳ ПРОГРАММА ЗАВЕРШИТСЯ ЧЕРЕЗ 10 СЕКУНД...")
    print("=" * 80)
    time.sleep(10)
