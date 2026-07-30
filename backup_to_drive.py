import os
import io
import zipfile
import datetime
from pathlib import Path

# Google API libraries
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
except ImportError:
    print("Google API libraries not found. Please install them using:")
    print("pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
    exit(1)

# Define paths
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"
UPLOADS_DIR = BASE_DIR / "static" / "uploads" / "products"
TOKEN_FILE = BASE_DIR / "token.json"
CREDENTIALS_FILE = BASE_DIR / "client_secret.json"

# Google Drive folder ID (leave empty to upload to root)
# The user can find this in the URL of their Google Drive folder: https://drive.google.com/drive/folders/YOUR_FOLDER_ID
DRIVE_FOLDER_ID = "1ss8jIbGSBwvEXOeXlwA5hICHxKRLrh-H"  # Update this if you want to upload to a specific folder

# Scopes required for Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_drive_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing access token...")
            creds.refresh(Request())
        else:
            print("ERROR: token.json is missing or invalid.")
            print("You must generate token.json locally and upload it to the server.")
            exit(1)
            
    return build('drive', 'v3', credentials=creds)

def create_backup_zip():
    print("Creating backup zip file in memory...")
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        if DB_PATH.exists():
            zf.write(DB_PATH, arcname='database.db')
        else:
            print(f"Warning: {DB_PATH} not found!")

        if UPLOADS_DIR.exists():
            for root, _, files in os.walk(UPLOADS_DIR):
                for file in files:
                    full_path = Path(root) / file
                    rel_path = full_path.relative_to(BASE_DIR)
                    zf.write(full_path, arcname=str(rel_path))
        else:
            print(f"Warning: {UPLOADS_DIR} not found!")
    
    memory_file.seek(0)
    return memory_file

def upload_to_drive(file_stream, filename):
    print("Authenticating with Google Drive API...")
    service = get_drive_service()

    file_metadata = {'name': filename}
    if DRIVE_FOLDER_ID:
        file_metadata['parents'] = [DRIVE_FOLDER_ID]

    print(f"Uploading {filename} to Google Drive...")
    media = MediaIoBaseUpload(file_stream, mimetype='application/zip', resumable=True)
    
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    
    print(f"Upload successful! File ID: {file.get('id')}")
    return True

if __name__ == "__main__":
    print(f"--- Starting Backup process at {datetime.datetime.now()} ---")
    zip_stream = create_backup_zip()
    
    today_str = datetime.date.today().isoformat()
    backup_filename = f"AK_Distributors_Backup_{today_str}.zip"
    
    upload_to_drive(zip_stream, backup_filename)
    print("--- Backup process completed ---")
