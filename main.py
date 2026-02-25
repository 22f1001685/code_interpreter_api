import sys
import traceback
from io import StringIO
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from google import genai
from google.genai import types

from openai import OpenAI
import json
import re

# ==============================
# 🔑 PUT YOUR AIPIPE TOKEN HERE
# ==============================
AIPIPE_API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IjIyZjEwMDE2ODVAZHMuc3R1ZHkuaWl0bS5hYy5pbiJ9.tMkhIuW5LJ3OJWCHKIFvD8J3Cv6k9VkQatCCRfFQYVs"

# ==============================
# 🚀 FastAPI App + CORS
# ==============================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================
# 📦 Request/Response Models
# ==============================
class CodeRequest(BaseModel):
    code: str


class ErrorAnalysis(BaseModel):
    error_lines: List[int]


class CodeResponse(BaseModel):
    error: List[int]
    result: str


# ==============================
# 🔧 Tool Function
# ==============================
def execute_python_code(code: str) -> dict:
    """
    Execute Python code and return exact output.
    """
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


# ==============================
# 🤖 AI Error Analysis
# ==============================
def analyze_error_with_ai(code: str, tb: str) -> List[int]:
    """
    Use LLM to identify error line numbers.
    """

    client = OpenAI(
        api_key=AIPIPE_API_KEY,
        base_url="https://aipipe.org/openai/v1",
    )

    prompt = f"""
You are a Python debugger.

Return ONLY valid JSON:

{{"error_lines": [line_numbers]}}

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

    text = response.choices[0].message.content

    # safe parse
    try:
        data = json.loads(text)
        return data.get("error_lines", [])
    except Exception:
        nums = re.findall(r"\d+", text)
        return [int(n) for n in nums] if nums else []

# ==============================
# 🌐 MAIN ENDPOINT
# ==============================
@app.post("/code-interpreter", response_model=CodeResponse)
def code_interpreter(request: CodeRequest):
    # Step 1: Execute code
    execution_result = execute_python_code(request.code)

    # Step 2: If success → no AI call
    if execution_result["success"]:
        return CodeResponse(
            error=[],
            result=execution_result["output"],
        )

    # Step 3: If error → AI analysis
    error_lines = analyze_error_with_ai(
        request.code,
        execution_result["output"],
    )

    # Step 4: Return final response
    return CodeResponse(
        error=error_lines,
        result=execution_result["output"],
    )


# ==============================
# ▶️ Run (optional)
# ==============================
# uvicorn main:app --reload