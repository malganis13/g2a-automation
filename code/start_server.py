# start_server.py - Запуск G2A FastAPI сервера
import subprocess
import sys
import os
from pathlib import Path


def main():
    print("=" * 60)
    print("    G2A FastAPI Server - Автозапуск")
    print("=" * 60)
    print()
    print("🚀 Запуск сервера...")
    print("📍 Порт: 80 (или 8000 если 80 занят)")
    print("🌐 URL: http://localhost:80")
    print()
    print("⚠️  НЕ ЗАКРЫВАЙТЕ ЭТО ОКНО!")
    print("   Сервер работает, пока окно открыто")
    print()
    print("=" * 60)
    print()

    # Путь к g2a_fastapi_server.py
    server_file = Path(__file__).parent / "g2a_fastapi_server.py"

    if not server_file.exists():
        print(f"❌ ОШИБКА: Файл {server_file} не найден!")
        input("Нажмите Enter для выхода...")
        sys.exit(1)

    # Запускаем сервер
    try:
        # Используем subprocess.run чтобы держать окно открытым
        process = subprocess.run(
            [sys.executable, str(server_file)],
            cwd=str(server_file.parent)
        )
    except KeyboardInterrupt:
        print("\n\n🛑 Остановка сервера...")
        print("✅ Сервер остановлен")
    except Exception as e:
        print(f"\n❌ Ошибка запуска сервера: {e}")
        input("\nНажмите Enter для выхода...")
        sys.exit(1)


if __name__ == "__main__":
    main()