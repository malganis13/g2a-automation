#!/bin/bash

echo "================================================"
echo "       G2A AUTOMATION - GUI Запуск"
echo "================================================"
echo ""

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден!"
    echo ""
    echo "👉 Установи Python3"
    exit 1
fi

echo "✅ Python3 найден"

# Проверка venv
if [ ! -d "venv" ]; then
    echo "🔧 Создаём виртуальное окружение..."
    python3 -m venv venv
    echo "✅ Venv создан"
fi

echo "✅ Активируем venv..."
source venv/bin/activate

# Установка зависимостей
if [ -f "requirements.txt" ]; then
    echo ""
    echo "🔍 Проверка зависимостей..."
    
    if ! python -c "import pydantic, loguru, httpx" 2>/dev/null; then
        echo ""
        echo "📦 Устанавливаем зависимости..."
        pip install -r requirements.txt --quiet
        echo "✅ Зависимости установлены"
    else
        echo "✅ Зависимости уже установлены"
    fi
fi

# Первая настройка
if [ ! -f ".env" ]; then
    echo ""
    echo "🔧 Первый запуск - настройка..."
    python setup_first_run.py
fi

echo ""
echo "🚀 Запускаем GUI..."
echo ""
python g2a_gui.py
