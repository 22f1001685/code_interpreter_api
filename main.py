import sys
import traceback
from io import StringIO
from typing import List
import os
import json
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI


AIPIPE_API_KEY = os.getenv("AIPIPE_API_KEY")


app = FastAPI(root_path="")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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

    try:
        data = json.loads(text)
        return data.get("error_lines", [])
    except Exception:
        nums = re.findall(r"\d+", text)
        return [int(n) for n in nums] if nums else []


@app.post("/code-interpreter", response_model=CodeResponse)
def code_interpreter(request: CodeRequest):
    execution_result = execute_python_code(request.code)

    if execution_result["success"]:
        return CodeResponse(error=[], result=execution_result["output"])

    error_lines = analyze_error_with_ai(
        request.code,
        execution_result["output"],
    )

    return CodeResponse(error=error_lines, result=execution_result["output"])