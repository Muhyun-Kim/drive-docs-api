from typing import List
from fastapi import FastAPI, Request, HTTPException, Query
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
from fastapi.responses import JSONResponse
import json

# .env 파일 로드
load_dotenv()

# 환경변수 읽기
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")
BEARER_TOKEN = os.getenv("DEFAULT_BEARER_TOKEN", "your-secret-token")
DOC_ID = os.getenv("DOC_ID", "docid.json")

SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# FastAPI 앱 생성
app = FastAPI()


# Bearer Token 검증 함수
def verify_token(request: Request):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = auth.split("Bearer ")[1]
    if token != BEARER_TOKEN:
        raise HTTPException(status_code=403, detail="Unauthorized access")


def load_doc_ids_from_json(key: str) -> list[str]:
    try:
        with open("docid.json", "r") as f:
            data = json.load(f)
        return data.get(key, [])
    except Exception as e:
        print(f"Failed to load doc IDs: {e}")
        return []


@app.get("/fetch-doc/dev-guide")
async def fetch_dev_guide_doc(request: Request):
    verify_token(request)

    doc_ids = load_doc_ids_from_json("dev_guide_docid")
    if not doc_ids:
        raise HTTPException(
            status_code=404, detail="No doc IDs found for dev_guide_docid"
        )

    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

    drive_service = build("drive", "v3", credentials=creds)
    contents = []

    for doc_id in doc_ids:
        try:
            file = drive_service.files().get(fileId=doc_id, fields="mimeType").execute()
            mime_type = file.get("mimeType")

            if mime_type == "application/vnd.google-apps.document":
                docs_service = build("docs", "v1", credentials=creds)
                doc = docs_service.documents().get(documentId=doc_id).execute()
                text = ""
                for element in doc.get("body", {}).get("content", []):
                    if "paragraph" in element:
                        for el in element["paragraph"].get("elements", []):
                            text += el.get("textRun", {}).get("content", "")
                contents.append(f"==== DOC ID: {doc_id} ====\n{text.strip()}")
            elif mime_type == "application/vnd.google-apps.spreadsheet":
                sheets_service = build("sheets", "v4", credentials=creds)
                sheet = (
                    sheets_service.spreadsheets()
                    .values()
                    .get(spreadsheetId=doc_id, range="A1:Z1000")
                    .execute()
                )
                rows = sheet.get("values", [])
                text = "\n".join(["\t".join(row) for row in rows])
                contents.append(f"==== DOC ID: {doc_id} ====\n{text.strip()}")
            else:
                contents.append(f"Unsupported file type for DOC ID: {doc_id}")
        except Exception as e:
            contents.append(f"Error reading DOC ID: {doc_id} - {str(e)}")

    return JSONResponse(content={"content": "\n\n".join(contents)})
