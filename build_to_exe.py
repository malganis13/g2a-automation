"""
Скрипт для компиляции G2A Automation Tool в .exe
Версия: 2.0 - С поддержкой сервера
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def install_pyinstaller():
    """Установка PyInstaller"""
    print("📦 Проверка PyInstaller...")
    try:
        import PyInstaller
        print(f"✅ PyInstaller уже установлен (версия {PyInstaller.__version__})")
        return True
    except ImportError:
        print("⏳ Установка PyInstaller...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            print("✅ PyInstaller установлен")
            return True
        except Exception as e:
            print(f"❌ Ошибка установки PyInstaller: {e}")
            return False


def build_gui():
    """Сборка главного GUI приложения"""
    print("\n" + "=" * 70)
    print("🎨 СБОРКА GUI ПРИЛОЖЕНИЯ")
    print("=" * 70 + "\n")

    app_name = "G2A_Tool"
    main_file = "g2a_gui.py"

    if not Path(main_file).exists():
        print(f"❌ Файл {main_file} не найден!")
        return False

    cmd = [
        "pyinstaller",
        "--name=" + app_name,
        "--onefile",
        "--windowed",  # БЕЗ консоли
        "--clean",
        "--noconfirm",
    ]

    # Иконка
    if Path("icon.ico").exists():
        cmd.append("--icon=icon.ico")
        print("🎨 Иконка: icon.ico")

    # Скрытые импорты для GUI
    hidden_imports = [
        "customtkinter",
        "PIL._tkinter_finder",
        "httpx",
        "curl_cffi",
        "curl_cffi.requests",
        "requests",
        "sqlite3",
        "asyncio",
        "threading",
        "json",
        "datetime",
        "tkinter",
        "tkinter.ttk",
        "tkinter.messagebox",
        "tkinter.filedialog",
        "tkinter.simpledialog",
        "g2a_config",
        "g2a_api_client",
        "price_parser",
        "database",
        "key_manager",
        "auto_price_changer",
        "telegram_notifier",
        "proxy_manager",
        "region_analyzer",
        "g2a_id_parser",
        "color_utils"
    ]

    print(f"\n📚 Скрытые импорты ({len(hidden_imports)} модулей):")
    for imp in hidden_imports:
        cmd.append(f"--hidden-import={imp}")
        print(f"   • {imp}")

    # Исключаем ненужное
    exclude = ["matplotlib", "numpy", "scipy", "pandas", "PyQt5", "PyQt6", "django", "flask"]
    for mod in exclude:
        cmd.append(f"--exclude-module={mod}")

    # Собираем всё из customtkinter
    cmd.append("--collect-all=customtkinter")

    cmd.append(main_file)

    print("\n⏳ Сборка GUI... (это займёт 2-5 минут)\n")

    try:
        subprocess.run(cmd, check=True)

        exe_path = Path("dist") / f"{app_name}.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"\n✅ GUI собран: {exe_path} ({size_mb:.2f} MB)")
            return True
        else:
            print("\n❌ GUI .exe не найден после сборки")
            return False

    except subprocess.CalledProcessError:
        print("\n❌ ОШИБКА СБОРКИ GUI!")
        return False


def build_server():
    """Сборка FastAPI сервера"""
    print("\n" + "=" * 70)
    print("🌐 СБОРКА API СЕРВЕРА")
    print("=" * 70 + "\n")

    app_name = "G2A_Server"
    main_file = "g2a_fastapi_server.py"

    if not Path(main_file).exists():
        print(f"❌ Файл {main_file} не найден!")
        return False

    cmd = [
        "pyinstaller",
        "--name=" + app_name,
        "--onefile",
        "--console",  # С консолью для логов
        "--clean",
        "--noconfirm",
    ]

    # Иконка для сервера
    if Path("server.ico").exists():
        cmd.append("--icon=server.ico")

    # Скрытые импорты для сервера
    hidden_imports = [
        "fastapi",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "pydantic",
        "httpx",
        "sqlite3",
        "asyncio",
        "g2a_config",
        "telegram_notifier"
    ]

    for imp in hidden_imports:
        cmd.append(f"--hidden-import={imp}")

    # Собираем всё из fastapi и uvicorn
    cmd.append("--collect-all=fastapi")
    cmd.append("--collect-all=uvicorn")

    cmd.append(main_file)

    print("⏳ Сборка сервера... (это займёт 2-3 минуты)\n")

    try:
        subprocess.run(cmd, check=True)

        exe_path = Path("dist") / f"{app_name}.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"\n✅ Сервер собран: {exe_path} ({size_mb:.2f} MB)")
            return True
        else:
            print("\n❌ Сервер .exe не найден после сборки")
            return False

    except subprocess.CalledProcessError:
        print("\n❌ ОШИБКА СБОРКИ СЕРВЕРА!")
        return False


def create_launcher():
    """Создание загрузчика"""
    print("\n" + "=" * 70)
    print("🚀 СОЗДАНИЕ ЗАГРУЗЧИКА")
    print("=" * 70 + "\n")

    launcher_code = '''import subprocess
import sys
import os
import time
from pathlib import Path

def main():
    print("=" * 70)
    print("       G2A AUTOMATION TOOL - ЗАГРУЗЧИК")
    print("=" * 70)
    print()
    
    # Определяем директорию с .exe
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
    else:
        exe_dir = Path(__file__).parent
    
    server_exe = exe_dir / "G2A_Server.exe"
    gui_exe = exe_dir / "G2A_Tool.exe"
    
    # Проверка наличия файлов
    if not server_exe.exists():
        print(f"❌ ОШИБКА: {server_exe.name} не найден!")
        print(f"   Путь: {server_exe}")
        input("\\nНажмите Enter для выхода...")
        return
    
    if not gui_exe.exists():
        print(f"❌ ОШИБКА: {gui_exe.name} не найден!")
        print(f"   Путь: {gui_exe}")
        input("\\nНажмите Enter для выхода...")
        return
    
    print("🌐 Запуск API сервера...")
    server_process = subprocess.Popen(
        [str(server_exe)],
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    
    print(f"   ✅ Сервер запущен (PID: {server_process.pid})")
    print("   ⏳ Ожидание инициализации (3 сек)...")
    time.sleep(3)
    
    print("\\n🖥️  Запуск главного приложения...")
    gui_process = subprocess.Popen([str(gui_exe)])
    
    print(f"   ✅ GUI запущен (PID: {gui_process.pid})")
    print()
    print("=" * 70)
    print("  ✅ G2A TOOL УСПЕШНО ЗАПУЩЕН!")
    print("=" * 70)
    print()
    print("  📌 Сервер работает в отдельном окне")
    print("  ⚠️  НЕ ЗАКРЫВАЙТЕ окно сервера!")
    print()
    print("  Это окно можно закрыть")
    print("=" * 70)
    
    # Ждём завершения GUI
    gui_process.wait()
    
    # После закрытия GUI - завершаем сервер
    print("\\n🛑 GUI закрыт. Остановка сервера...")
    server_process.terminate()
    server_process.wait()
    print("✅ Все процессы остановлены")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\\n\\n⏹️ Прервано пользователем")
    except Exception as e:
        print(f"\\n❌ Ошибка: {e}")
        input("\\nНажмите Enter для выхода...")
'''

    launcher_file = "launcher.py"
    with open(launcher_file, 'w', encoding='utf-8') as f:
        f.write(launcher_code)

    cmd = [
        "pyinstaller",
        "--name=G2A_Start",
        "--onefile",
        "--console",
        "--clean",
        "--noconfirm",
        launcher_file
    ]

    if Path("launcher.ico").exists():
        cmd.append("--icon=launcher.ico")

    print("⏳ Сборка загрузчика...\n")

    try:
        subprocess.run(cmd, check=True)

        exe_path = Path("dist") / "G2A_Start.exe"
        if exe_path.exists():
            print(f"\n✅ Загрузчик создан: {exe_path}")
            return True
        else:
            print("\n❌ Загрузчик не найден после сборки")
            return False

    except subprocess.CalledProcessError:
        print("\n❌ ОШИБКА СОЗДАНИЯ ЗАГРУЗЧИКА!")
        return False


def copy_files():
    """Копирование необходимых файлов в dist"""
    print("\n" + "=" * 70)
    print("📋 КОПИРОВАНИЕ ДОПОЛНИТЕЛЬНЫХ ФАЙЛОВ")
    print("=" * 70 + "\n")

    dist_dir = Path("dist")

    # Файлы для копирования
    files_to_copy = [
        "g2a_config_saved.json",
        "auto_price_settings.json",
        "daily_limit.json",
        "keys.db",
        "proxy.txt"
    ]

    for file in files_to_copy:
        if Path(file).exists():
            shutil.copy(file, dist_dir / file)
            print(f"   ✅ Скопирован: {file}")
        else:
            print(f"   ⚠️  Пропущен (не найден): {file}")

    # Создаём папки
    for folder in ['keys', 'result', 'logs']:
        folder_path = dist_dir / folder
        folder_path.mkdir(exist_ok=True)
        print(f"   ✅ Создана папка: {folder}")


def clean_build():
    """Очистка временных файлов"""
    print("\n🧹 Очистка временных файлов...")

    folders = ["build", "__pycache__"]
    for folder in folders:
        if Path(folder).exists():
            shutil.rmtree(folder)
            print(f"   Удалена папка: {folder}")

    import glob
    for spec_file in glob.glob("*.spec"):
        os.remove(spec_file)
        print(f"   Удален файл: {spec_file}")

    # Удаляем launcher.py
    if Path("launcher.py").exists():
        os.remove("launcher.py")
        print(f"   Удален файл: launcher.py")

    print("✅ Очистка завершена\n")


def main():
    """Главная функция"""
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║        G2A AUTOMATION TOOL - СБОРКА В .EXE (ПОЛНАЯ)             ║
║                                                                   ║
║  Эта программа скомпилирует все компоненты в .exe файлы:        ║
║  • G2A_Tool.exe      (главное приложение)                       ║
║  • G2A_Server.exe    (API сервер)                               ║
║  • G2A_Start.exe     (загрузчик - запускает всё)               ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
    """)

    if not install_pyinstaller():
        input("Нажмите Enter для выхода...")
        return

    success = True

    # Сборка GUI
    if not build_gui():
        success = False

    # Сборка сервера
    if not build_server():
        success = False

    # Создание загрузчика
    if success and not create_launcher():
        success = False

    # Копирование файлов
    if success:
        copy_files()

    if success:
        response = input("\n🧹 Удалить временные файлы сборки? (y/n): ").strip().lower()
        if response == 'y':
            clean_build()

        print("\n" + "=" * 70)
        print("🎉 СБОРКА ЗАВЕРШЕНА УСПЕШНО!")
        print("=" * 70)
        print("\nСозданные файлы в папке dist/:")
        print("  1. G2A_Start.exe     ← ЗАПУСКАЙТЕ ЭТОТ ФАЙЛ")
        print("  2. G2A_Tool.exe      (главное приложение)")
        print("  3. G2A_Server.exe    (API сервер)")
        print("\n💡 ИСПОЛЬЗОВАНИЕ:")
        print("  • Запустите G2A_Start.exe - это запустит сервер и GUI")
        print("  • Или запускайте вручную: сначала G2A_Server.exe, затем G2A_Tool.exe")
        print("\n📦 Можете перенести всю папку dist/ на другой компьютер")
        print("   (Python и зависимости не нужны)")
        print("=" * 70 + "\n")
    else:
        print("\n" + "=" * 70)
        print("❌ СБОРКА НЕ УДАЛАСЬ")
        print("=" * 70)
        print("\nПроверьте ошибки выше\n")

    input("Нажмите Enter для выхода...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️ Сборка отменена пользователем")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        input("Нажмите Enter для выхода...")