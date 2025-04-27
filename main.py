from typing import List
from fastapi import FastAPI, Request, HTTPException, Query
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os

# .env 파일 로드
load_dotenv()

# 환경변수 읽기
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")
BEARER_TOKEN = os.getenv("DEFAULT_BEARER_TOKEN", "your-secret-token")

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


# 여러 문서 읽기 API
@app.get("/fetch-doc")
async def fetch_doc(request: Request, doc_ids: List[str] = Query(...)):
    verify_token(request)

    # 서비스 계정 인증
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

    drive_service = build("drive", "v3", credentials=creds)
    docs_service = build("docs", "v1", credentials=creds)
    sheets_service = build("sheets", "v4", credentials=creds)

    combined_text = ""

    for doc_id in doc_ids:
        # mimeType 확인
        file = drive_service.files().get(fileId=doc_id, fields="mimeType").execute()
        mime_type = file.get("mimeType")

        text = ""

        if mime_type == "application/vnd.google-apps.document":
            # Google Docs 읽기
            doc = docs_service.documents().get(documentId=doc_id).execute()
            for element in doc.get("body", {}).get("content", []):
                if "paragraph" in element:
                    for el in element["paragraph"].get("elements", []):
                        text += el.get("textRun", {}).get("content", "")
        elif mime_type == "application/vnd.google-apps.spreadsheet":
            # Google Sheets 읽기
            sheet = (
                sheets_service.spreadsheets()
                .values()
                .get(spreadsheetId=doc_id, range="A1:Z1000")
                .execute()
            )
            rows = sheet.get("values", [])
            text = "\n".join(["\t".join(row) for row in rows])
        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported file type for doc_id: {doc_id}"
            )

        combined_text += f"\n\n=== DOC ID: {doc_id} ===\n\n{text.strip()}"

    return {"content": combined_text.strip()}
