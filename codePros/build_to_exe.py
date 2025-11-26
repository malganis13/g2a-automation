# build_to_exe.py - ФИНАЛЬНЫЙ РАБОЧИЙ ВАРИАНТ
# Простой, проверенный, работающий!

import os
import shutil
import subprocess
import sys

print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                    🔨 СБОРКА ПРОЕКТА В EXE 🔨                           ║
║                         ФИНАЛЬНАЯ ВЕРСИЯ v1.0                            ║
╚════════════════════════════════════════════════════════════════════════════╝
""")

# ОЧИСТКА
print("\n🧹 Этап 1: Очистка старых файлов...")
for folder in ['build', 'dist']:
    if os.path.exists(folder):
        shutil.rmtree(folder)
        print(f"   ✅ Удалена папка: {folder}")

print("   ✅ Очистка завершена\n")

# СБОРКА GUI
print("="*80)
print("📱 Этап 2: Сборка GUI (G2A_Automation.exe)")
print("="*80)

gui_cmd = [
    'pyinstaller',
    '--onefile',
    '--windowed',
    '--name', 'G2A_Automation',
    '--distpath', 'dist',
    'g2a_gui.py'
]

try:
    print("⏳ Компилирую G2A_Automation.exe...")
    result = subprocess.run(gui_cmd, check=False, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ GUI собран успешно!\n")
    else:
        print("❌ Ошибка сборки GUI:")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)
except Exception as e:
    print(f"❌ Исключение при сборке GUI: {e}")
    sys.exit(1)

# СБОРКА СЕРВЕРА
print("="*80)
print("🖥️  Этап 3: Сборка Сервера (G2A_Server.exe)")
print("="*80)

server_cmd = [
    'pyinstaller',
    '--onefile',
    '--name', 'G2A_Server',
    '--distpath', 'dist',
    'g2a_fastapi_server.py'
]

try:
    print("⏳ Компилирую G2A_Server.exe...")
    result = subprocess.run(server_cmd, check=False, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Сервер собран успешно!\n")
    else:
        print("❌ Ошибка сборки сервера:")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)
except Exception as e:
    print(f"❌ Исключение при сборке сервера: {e}")
    sys.exit(1)

# СБОРКА MAIN
print("="*80)
print("⚙️  Этап 4: Сборка Main (G2A_Main.exe) - опционально")
print("="*80)

main_cmd = [
    'pyinstaller',
    '--onefile',
    '--name', 'G2A_Main',
    '--distpath', 'dist',
    'main.py'
]

try:
    print("⏳ Компилирую G2A_Main.exe...")
    result = subprocess.run(main_cmd, check=False, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Main собран успешно!\n")
    else:
        print("⚠️  Main не собран (может быть не требуется)\n")
except Exception as e:
    print(f"⚠️  Ошибка при сборке main: {e}\n")

# КОПИРОВАНИЕ КОНФИГОВ
print("="*80)
print("📋 Этап 5: Копирование конфигов в dist/")
print("="*80)

copied = 0
for config in ['g2a_config.json', 'daily_limit.json']:
    if os.path.exists(config):
        shutil.copy(config, os.path.join('dist', config))
        print(f"   ✅ Скопирован: {config}")
        copied += 1
    else:
        print(f"   ℹ️  {config} не найден (будет создан при запуске)")

print(f"\n   ✅ Скопировано {copied} файлов\n")

# ФИНАЛЬНАЯ ИНФОРМАЦИЯ
print("="*80)
print("✅ СБОРКА ЗАВЕРШЕНА УСПЕШНО!")
print("="*80)

import os
dist_files = os.listdir('dist') if os.path.exists('dist') else []
exe_files = [f for f in dist_files if f.endswith('.exe')]

print(f"""
📦 В папке dist/ готовы следующие файлы:

""")

for exe in exe_files:
    size_kb = os.path.getsize(os.path.join('dist', exe)) / 1024
    print(f"   ✅ {exe:30} ({size_kb:.1f} KB)")

print(f"""
🚀 КАК ИСПОЛЬЗОВАТЬ:

   1. Открой папку dist/
   
   2. Запусти G2A_Server.exe ПЕРВЫМ:
      • Откроется окно сервера
      • Оставь его открытым
      
   3. Запусти G2A_Automation.exe ВТОРЫМ:
      • Откроется главное приложение
      
   4. Программа готова к работе!

⚠️  ВАЖНО:
   • Убедись что g2a_config.json в папке dist/
   • Убедись что daily_limit.json в папке dist/
   • Если файлов нет - они создадутся автоматически
   
════════════════════════════════════════════════════════════════════════════════

✅ ВСЁ ГОТОВО! Можешь закрыть это окно и использовать программу!
""")

input("Нажми Enter для выхода...")
