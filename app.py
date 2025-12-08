from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import json
import os
import requests
from uuid import uuid4
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENROUTER_API_KEY = "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"
MODEL_NAME = "gpt-4o-mini"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

class FileId(BaseModel):
    file_id: str

@app.get("/")
def home():
    return {"status": "running"}

def extract_text(path):
    text = ""
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            t = p.extract_text()
            if t:
                text += t + "\n"
    return text[:4000]

def ask_llm(text):
    prompt = f"""
Generate 10 ONLY relevant FAQs based strictly on the content below.
Each FAQ must be factual and derived from the PDF, not generic.

Return EXACT JSON array format:

[
  {{"question": "?", "answer": "?"}}
]

Text:
{text}
"""

    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 600
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    }

    res = requests.post(OPENROUTER_URL, json=payload, headers=headers)

    if res.status_code != 200:
        print("LLM ERROR:", res.text)
        return None

    content = res.json()['choices'][0]['message']['content']
    content = content.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(content)
    except:
        print("LLM JSON ERROR:", content)
        return None

@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "PDF only")

    os.makedirs("uploaded", exist_ok=True)
    file_id = str(uuid4())
    path = f"uploaded/{file_id}.pdf"

    with open(path, "wb") as f:
        f.write(await file.read())

    return {"id": file_id, "path": path}

@app.post("/generate-faq")
async def generate_faq(data: FileId):
    path = f"uploaded/{data.file_id}.pdf"

    if not os.path.exists(path):
        return {"error": "PDF missing", "faqs": []}

    text = extract_text(path)
    faqs = ask_llm(text)

    if faqs is None:
        return {"error": "LLM failed", "faqs": []}

    return {"faqs": faqs}
