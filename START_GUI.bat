@echo off
chcp 65001 >nul
echo ================================================
echo       G2A AUTOMATION - GUI Запуск
echo ================================================
echo.

REM Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден!
    echo.
    echo 👉 Установи Python: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo ✅ Python найден
echo.

REM Проверка venv
if not exist "venv\Scripts\activate.bat" (
    echo 🔧 Создаём виртуальное окружение...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ Ошибка создания venv
        pause
        exit /b 1
    )
    echo ✅ Venv создан
)

echo ✅ Активируем venv...
call venv\Scripts\activate.bat

REM Проверка зависимостей
if exist "requirements.txt" (
    echo.
    echo 🔍 Проверка зависимостей...
    python -c "import pydantic, loguru, httpx" 2>nul
    if errorlevel 1 (
        echo.
        echo 📦 Устанавливаем зависимости...
        pip install -r requirements.txt --quiet
        if errorlevel 1 (
            echo ❌ Ошибка установки зависимостей
            pause
            exit /b 1
        )
        echo ✅ Зависимости установлены
    ) else (
        echo ✅ Зависимости уже установлены
    )
)

REM Первая настройка
if not exist ".env" (
    echo.
    echo 🔧 Первый запуск - настройка...
    python setup_first_run.py
)

echo.
echo 🚀 Запускаем GUI...
echo.
python g2a_gui.py

if errorlevel 1 (
    echo.
    echo ❌ Ошибка запуска!
    pause
)
