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
