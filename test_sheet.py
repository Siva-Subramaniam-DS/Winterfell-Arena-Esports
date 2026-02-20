import gspread
from google.oauth2.service_account import Credentials
import os

SERVICE_ACCOUNT_FILE = "service_account.json"
GOOGLE_SHEET_ID = "1i8yWJhe-T4cYQtrzfp4HcqH8UmndDi8yydWnMYDfcMI"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def test_connection():
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print("NO: service_account.json file not found.")
        return

    try:
        credentials = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        client = gspread.authorize(credentials)
        sheet = client.open_by_key(GOOGLE_SHEET_ID)
        print("YES: Successfully connected to Google Sheet.")
        print(f"Sheet Title: {sheet.title}")
    except Exception as e:
        print(f"NO: Error connecting to Google Sheet: {repr(e)}")
        if "404" in str(e):
            print("Make sure the Sheet ID is correct and the sheet exists.")
        if "403" in str(e):
            print("Permission denied. Make sure the service account email has been added as an Editor.")

if __name__ == "__main__":
    test_connection()
