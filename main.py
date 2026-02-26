import sys
import traceback
from io import StringIO
from typing import List
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


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
        # Run in isolated namespace
        exec(code, {})
        output = sys.stdout.getvalue()
        return {"success": True, "output": output}
    except Exception:
        output = traceback.format_exc()
        return {"success": False, "output": output}
    finally:
        sys.stdout = old_stdout


def extract_error_line(traceback_text: str) -> List[int]:
    """
    Extract only the actual failing line from traceback.
    Works reliably for Render environment.
    """

    if "Traceback" not in traceback_text:
        return []

    lines = traceback_text.splitlines()

    error_line = None

    for line in lines:
        if 'File "<string>"' in line:
            parts = line.split("line ")
            if len(parts) > 1:
                try:
                    error_line = int(parts[1].split(",")[0])
                except:
                    pass

    if error_line is not None:
        return [error_line]

    return []


@app.post("/code-interpreter", response_model=CodeResponse)
def code_interpreter(request: CodeRequest):
    execution_result = execute_python_code(request.code)

    if execution_result["success"]:
        return CodeResponse(error=[], result=execution_result["output"])

    error_lines = extract_error_line(execution_result["output"])

    return CodeResponse(error=error_lines, result=execution_result["output"])