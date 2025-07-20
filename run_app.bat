@echo off

REM Устанавливаем путь к credentials.json
set GOOGLE_APPLICATION_CREDENTIALS=D:\PycharmProjects\PythonProject\Internet_store\secrets\credentials.json

REM Устанавливаем ID таблицы
set GOOGLE_SPREADSHEET_ID=1GgDUd9YdVdmXGOzrhu6eYrFVeQhk7fG13ZhB3T9rc3E

REM Активация виртуального окружения
call D:\PycharmProjects\PythonProject\Internet_store\.venv\Scripts\activate

REM Запуск приложения
python D:\PycharmProjects\PythonProject\Internet_store\app.py

pause