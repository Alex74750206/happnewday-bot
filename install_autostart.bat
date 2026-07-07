@echo off
chcp 65001 >nul
echo ============================================
echo   Бот "Песня в подарок" — автозапуск
echo ============================================
echo.

set TASK_NAME=HappnewdayBot
set BOT_DIR=%~dp0
set LOG_OUT=%BOT_DIR%bot_out.log
set LOG_ERR=%BOT_DIR%bot_err.log

:: Удаляем старую задачу если была
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Создаём задачу: запуск при входе в систему с задержкой 30 сек
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "cmd.exe /c \"cd /d \"%BOT_DIR%\" && python main.py >> \"%LOG_OUT%\" 2>> \"%LOG_ERR%\"\"" ^
  /sc ONLOGON ^
  /delay 0000:30 ^
  /rl HIGHEST ^
  /f >nul

if %errorlevel% neq 0 (
    echo [ОШИБКА] Не удалось создать задачу в Планировщике.
    echo Попробуйте запустить этот файл от имени Администратора.
    pause
    exit /b 1
)

echo [OK] Задача "%TASK_NAME%" создана в Планировщике задач.
echo      Бот будет автоматически запускаться при входе в Windows.
echo.
echo Для удаления автозапуска:
echo   schtasks /delete /tn "%TASK_NAME%" /f
echo.
pause
