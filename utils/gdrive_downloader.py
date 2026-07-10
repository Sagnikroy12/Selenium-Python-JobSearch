import io
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


# mimeTypes that are Google Workspace native formats and need export, not download
_EXPORTABLE_MIME_MAP = {
    "application/vnd.google-apps.document": "application/pdf",
    "application/vnd.google-apps.presentation": "application/pdf",
}


def download_resume(file_id: str, dest_path: str, service_account_json_path: str):
    """Downloads a resume file from Google Drive by its file ID using a service account key.
    
    Handles both binary files (PDF, DOCX) and Google-native documents (Docs → export as PDF).
    Raises an explicit error if the service account cannot access the file.
    """
    print(f"Initializing Google Drive service with credentials: {service_account_json_path}")
    
    creds = service_account.Credentials.from_service_account_file(
        service_account_json_path,
        scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    service = build("drive", "v3", credentials=creds)
    
    # Step 1: Fetch file metadata to verify access and check type
    print(f"Fetching metadata for file ID: {file_id}")
    meta = service.files().get(fileId=file_id, fields="id, name, mimeType").execute()
    mime_type = meta.get("mimeType", "")
    drive_name = meta.get("name", "unknown")
    print(f"  Drive filename : '{drive_name}'")
    print(f"  MIME type      : {mime_type}")

    dest_dir = os.path.dirname(dest_path)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    with open(dest_path, "wb") as fh:
        if mime_type in _EXPORTABLE_MIME_MAP:
            # Google native format: export as PDF
            export_mime = _EXPORTABLE_MIME_MAP[mime_type]
            print(f"  Exporting as PDF (source is {mime_type})")
            request = service.files().export_media(fileId=file_id, mimeType=export_mime)
        else:
            # Binary file (PDF, DOCX, etc.)
            print(f"  Downloading binary file directly")
            request = service.files().get_media(fileId=file_id)

        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"  Download progress: {int(status.progress() * 100)}%")
            
    print(f"Download complete! Saved to: {dest_path}")
