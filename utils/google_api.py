import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Скоупы
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Переменные окружения
credentials_json = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_JSON')
spreadsheet_id = os.environ.get('GOOGLE_SPREADSHEET_ID')

if not credentials_json or not spreadsheet_id:
    raise Exception("❌ Не найдены переменные окружения GOOGLE_APPLICATION_CREDENTIALS_JSON или GOOGLE_SPREADSHEET_ID.")

# Чтение JSON из переменной и подключение к API
credentials_info = json.loads(credentials_json)
creds = service_account.Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

# Чтение таблицы
def read_sheet(range_name):
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    return result.get('values', [])

# Добавление строк
def write_sheet(range_name, values):
    body = {'values': values}
    result = sheet.values().append(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='USER_ENTERED',
        insertDataOption='INSERT_ROWS',
        body=body
    ).execute()
    return result

# Перезапись диапазона
def update_sheet_range(range_name, values):
    body = {'values': values}
    sheet.values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='RAW',
        body=body
    ).execute()

# Очистка диапазона
def clear_sheet_range(range_name):
    sheet.values().clear(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        body={}
    ).execute()

# Получение последнего номера заказа
def get_max_order_number():
    result = sheet.values().get(
        spreadsheetId=spreadsheet_id,
        range='Orders!C3:C'
    ).execute()
    values = result.get('values', [])
    numbers = [int(v[0]) for v in values if v and v[0].isdigit()]
    return max(numbers) if numbers else 0

