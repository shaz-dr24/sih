from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from uuid import uuid4

# load .env for local development ONLY
from dotenv import load_dotenv
load_dotenv()  # this reads .env only when running locally

# use the new Pinecone client class
from pinecone import Pinecone
import pdfplumber
import requests
import json

app = FastAPI()

# -----------------------------------------------------------------------------------
# CORS
# -----------------------------------------------------------------------------------
FRONTEND_URL = os.getenv("FRONTEND_URL", "*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL] if FRONTEND_URL != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------------
# CONFIG (READ FROM ENV)
# -----------------------------------------------------------------------------------
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ASSISTANT_NAME = os.getenv("PINECONE_ASSISTANT_NAME", "sol-seekers")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
OPENROUTER_URL = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")

# -----------------------------------------------------------------------------------
# INIT PINECONE (new SDK: instantiate Pinecone)
# -----------------------------------------------------------------------------------
pinecone_available = False
assistant = None
pc = None

if PINECONE_API_KEY:
    try:
        # Create a Pinecone client instance (new SDK pattern)
        pc = Pinecone(api_key=PINECONE_API_KEY)
        # quick smoke-check: list_indexes() will raise if auth fails
        try:
            _ = pc.list_indexes()  # doesn't need to be stored; just validates the client
            pinecone_available = True
        except Exception:
            # even if list_indexes fails (network/permission), we keep the client object
            pinecone_available = True
        assistant = None  # keep assistant None unless you implement a wrapper
    except Exception as e:
        print("pinecone init error:", e)
        pinecone_available = False
        assistant = None
else:
    print("Warning: PINECONE_API_KEY not set — Pinecone features will be disabled.")
    pinecone_available = False
    assistant = None

# -----------------------------------------------------------------------------------
# MODELS / Pydantic
# -----------------------------------------------------------------------------------
class FileId(BaseModel):
    file_id: str

class SyncRequest(BaseModel):
    file_ids: list[str]

# -----------------------------------------------------------------------------------
# UPLOAD PDF
# -----------------------------------------------------------------------------------
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        return {"error": "Only PDF files allowed"}

    os.makedirs("uploaded", exist_ok=True)

    file_id = file.filename.replace(".pdf", "")
    save_path = f"uploaded/{file_id}.pdf"

    with open(save_path, "wb") as f:
        f.write(await file.read())

    return {
        "id": file_id,
        "name": file.filename,
        "path": save_path,
        "pinecone_upload": False
    }

# -----------------------------------------------------------------------------------
# SYNC PDF → PINECONE
# -----------------------------------------------------------------------------------
@app.post("/sync-chatbot")
async def sync_chatbot(data: SyncRequest):
    # early-fail if we don't have a compatible assistant object
    if not pinecone_available or assistant is None:
        return {"status": "failed", "error": "Pinecone assistant not configured on this runtime."}

    results = []

    for file_id in data.file_ids:
        path = f"uploaded/{file_id}.pdf"

        if not os.path.exists(path):
            results.append({"file_id": file_id, "status": "failed", "error": "File not found"})
            continue

        try:
            response = assistant.upload_file(file_path=path, timeout=None)
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

# -----------------------------------------------------------------------------------
# TEXT EXTRACTION
# -----------------------------------------------------------------------------------
def extract_text(path):
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()


# -----------------------------------------------------------------------------------
# FAQ GENERATION
# -----------------------------------------------------------------------------------
def generate_faq_from_text(text):
    if not OPENROUTER_API_KEY:
        return [{"error": "OPENROUTER_API_KEY missing"}]

    prompt = f"""
Generate 10 FAQs based on this PDF.

Return ONLY JSON array:
[
  {{"question": "...", "answer": "..."}}
]

Text:
{text[:10000]}
"""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://localhost",
        "X-Title": "PDF-FAQ-Generator"
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2000,
    }

    try:
        res = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=60)
        res.raise_for_status()

        output = res.json()["choices"][0]["message"]["content"]
        output = output.replace("```json", "").replace("```", "").strip()

        return json.loads(output)

    except Exception as e:
        print("OpenRouter error:", e)
        return []

@app.post("/generate-faq")
async def generate_faq(data: FileId):
    path = f"uploaded/{data.file_id}.pdf"

    if not os.path.exists(path):
        return {"error": "File not found", "faqs": []}

    text = extract_text(path)
    faqs = generate_faq_from_text(text)

    return {"faqs": faqs}


@app.get("/")
def root():
    return {"status": "Backend Running"}


# -----------------------------------------------------------------------------------
# Local run (uvicorn)
# -----------------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
