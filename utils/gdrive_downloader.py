import io
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


def download_resume(file_id: str, dest_path: str, service_account_json_path: str):
    """Downloads a resume file from Google Drive by its file ID using a service account key."""
    print(f"Initializing Google Drive service with credentials: {service_account_json_path}")
    
    creds = service_account.Credentials.from_service_account_file(
        service_account_json_path,
        scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    service = build("drive", "v3", credentials=creds)
    
    print(f"Requesting file media for file ID: {file_id}")
    request = service.files().get_media(fileId=file_id)
    
    dest_dir = os.path.dirname(dest_path)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)
        
    with open(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download progress: {int(status.progress() * 100)}%")
            
    print(f"Download complete! Saved to: {dest_path}")
