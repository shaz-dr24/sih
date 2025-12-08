from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from uuid import uuid4
from pinecone import Pinecone
import pdfplumber
import requests
import json

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CONFIG
PINECONE_API_KEY = "pcsk_7VvikS_FXDU4maCLtEYh2USAzmY6wWFhQa6KPFYFwQ248JH5tBVhibXMwBMnJKuFMPMtcH"
PINECONE_ASSISTANT_NAME = "sol-seekers"

OPENROUTER_API_KEY = "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"
MODEL_NAME = "gpt-4o-mini"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# INIT PINECONE
pc = Pinecone(api_key=PINECONE_API_KEY)
assistant = pc.assistant.Assistant(assistant_name=PINECONE_ASSISTANT_NAME)

# MODELS
class FileId(BaseModel):
    file_id: str

class SyncRequest(BaseModel):
    file_ids: list[str]   # <-- match frontend
   # {id, name}


# -------------------------------
# UPLOAD PDF (LOCAL ONLY)
# -------------------------------
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        return {"error": "Only PDF allowed"}

    os.makedirs("uploaded", exist_ok=True)
    original_name = file.filename
    save_path = f"uploaded/{original_name}"
    file_id = original_name.replace(".pdf", "")

    path = f"uploaded/{file_id}.pdf"

    with open(path, "wb") as f:
        f.write(await file.read())

    return {
        "id": file_id,
        "name": file.filename,
        "path": path,
        "pinecone_upload": False
    }


# -------------------------------
# SYNC PDFs TO PINECONE (WORKS 100%)
# -------------------------------
@app.post("/sync-chatbot")
async def sync_chatbot(data: SyncRequest):
    results = []

    for file_id in data.file_ids:
        full_path = f"uploaded/{file_id}.pdf"

        if not os.path.exists(full_path):
            results.append({
                "file_id": file_id,
                "status": "failed",
                "error": "File not found"
            })
            continue

        try:
            response = assistant.upload_file(
                file_path=full_path,
                timeout=None
            )

            results.append({
                "file_id": file_id,
                "status": "uploaded",
                "pinecone_response": str(response)
            })

        except Exception as e:
            results.append({
                "file_id": file_id,
                "status": "failed",
                "error": str(e)
            })

    return {"status": "complete", "results": results}



# -------------------------------
# EXTRACT TEXT
# -------------------------------
def extract_text(path):
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text.strip()


# -------------------------------
# GENERATE FAQ
# -------------------------------
def generate_faq_from_text(text):
    prompt = f"""
Generate 10 FAQs based on this PDF:

Return ONLY JSON:
[
  {{"question": "...", "answer": "..."}}
]

Text:
{text[:10000]}
"""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost",
        "X-Title": "PDF-FAQ-Generator"
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2000,
    }

    try:
        res = requests.post(OPENROUTER_URL, json=payload, headers=headers)
        out = res.json()["choices"][0]["message"]["content"]
        out = out.replace("```json", "").replace("```", "").strip()
        return json.loads(out)
    except:
        return []


@app.post("/generate-faq")
async def gen_faq(data: FileId):
    path = f"uploaded/{data.file_id}.pdf"

    if not os.path.exists(path):
        return {"error": "Not found", "faqs": []}

    text = extract_text(path)
    faqs = generate_faq_from_text(text)

    return {"faqs": faqs}


@app.get("/")
def root():
    return {"status": "Backend Running"}
