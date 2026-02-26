import sys
import traceback
from io import StringIO
from typing import List
import os
import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI


AIPIPE_API_KEY = os.getenv("AIPIPE_API_KEY")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CodeRequest(BaseModel):
    code: str


class CodeResponse(BaseModel):
    error: List[int]
    result: str


def execute_python_code(code: str) -> dict:
    old_stdout = sys.stdout
    sys.stdout = StringIO()

    try:
        exec(code)
        output = sys.stdout.getvalue()
        return {"success": True, "output": output}
    except Exception:
        output = traceback.format_exc()
        return {"success": False, "output": output}
    finally:
        sys.stdout = old_stdout


def analyze_error_with_ai(code: str, tb: str) -> List[int]:
    client = OpenAI(
        api_key=AIPIPE_API_KEY,
        base_url="https://aipipe.org/openai/v1",
    )

    prompt = f"""
You are a Python debugger.

Return ONLY valid JSON in this format:
{{"error_lines": [line_numbers]}}

Line numbers start from 1.
Only return the line where the actual exception occurred.

CODE:
{code}

TRACEBACK:
{tb}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    text = response.choices[0].message.content.strip()

    # Strict JSON parsing only
    try:
        data = json.loads(text)
        if isinstance(data.get("error_lines"), list):
            return data["error_lines"]
        return []
    except Exception:
        # If model returns invalid JSON, return empty to avoid false positives
        return []


@app.post("/code-interpreter", response_model=CodeResponse)
def code_interpreter(request: CodeRequest):
    execution_result = execute_python_code(request.code)

    # ✅ Only call AI if execution actually failed
    if execution_result["success"]:
        return CodeResponse(
            error=[],
            result=execution_result["output"],
        )

    error_lines = analyze_error_with_ai(
        request.code,
        execution_result["output"],
    )

    return CodeResponse(
        error=error_lines,
        result=execution_result["output"],
    )

# ===============================
# Health check
# ===============================
@app.get("/")
def health():
    return {"status": "ok"}