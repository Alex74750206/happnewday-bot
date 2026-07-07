@echo off
chcp 65001 >nul
echo ============================================
echo   Бот "Песня в подарок" — запуск
echo ============================================
echo.

:: Проверяем .env
if not exist .env (
    echo [ОШИБКА] Файл .env не найден. Сначала запустите setup.bat
    pause
    exit /b 1
)

:: Проверяем что ключи заполнены
findstr /C:"your_telegram_bot_token_here" .env >nul 2>&1
if not errorlevel 1 (
    echo [ОШИБКА] В .env не заполнен TELEGRAM_BOT_TOKEN
    echo Откройте .env и вставьте настоящие ключи.
    pause
    exit /b 1
)

echo Запускаю бота... (Ctrl+C для остановки)
echo.
python main.py

echo.
echo Бот остановлен.
pause
