from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '1GgDUd9YdVdmXGOzrhu6eYrFVeQhk7fG13ZhB3T9rc3E'

creds = service_account.Credentials.from_service_account_file(
    'utils/credentials.json', scopes=SCOPES)

service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

def read_sheet(range_name):
    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=range_name).execute()
    return result.get('values', [])


def write_sheet(range_name, values):
    body = {'values': values}
    result = sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=range_name,
        valueInputOption='USER_ENTERED',
        body=body
    ).execute()
    return result


def get_max_order_number():
    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range='Orders!B3:B'
    ).execute()
    values = result.get('values', [])
    numbers = [int(v[0]) for v in values if v and v[0].isdigit()]
    return max(numbers) if numbers else 0