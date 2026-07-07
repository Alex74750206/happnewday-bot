@echo off
chcp 65001 >nul
echo ============================================
echo   Настройка бота "Песня в подарок"
echo ============================================
echo.

:: Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден. Установите Python 3.10+ с python.org
    pause
    exit /b 1
)

:: Устанавливаем зависимости
echo [1/2] Устанавливаем зависимости...
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ОШИБКА] Не удалось установить зависимости.
    pause
    exit /b 1
)

:: Создаём .env если его нет
if not exist .env (
    echo [2/2] Создаём файл .env из шаблона...
    copy .env.example .env >nul
    echo.
    echo [ВАЖНО] Откройте файл .env и заполните три ключа:
    echo   TELEGRAM_BOT_TOKEN — токен от @BotFather
    echo   CLAUDE_API_KEY     — ключ с console.anthropic.com
    echo   KIE_API_KEY        — ключ с kie.ai
    echo.
    echo После заполнения .env запустите start.bat
) else (
    echo [2/2] Файл .env уже существует — пропускаем.
)

echo.
echo ============================================
echo   Установка завершена!
echo ============================================
pause
