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
        exec(code)
        output = sys.stdout.getvalue()
        return {"success": True, "output": output}

    except Exception:
        output = traceback.format_exc()
        return {"success": False, "output": output}

    finally:
        sys.stdout = old_stdout


def extract_error_line(traceback_str: str) -> List[int]:
    """
    Extract the most relevant error line from traceback.
    We specifically look for: File "<string>", line X
    """
    matches = re.findall(r'File "<string>", line (\d+)', traceback_str)

    if matches:
        # Return the last occurrence (actual error location)
        return [int(matches[-1])]

    return []


@app.post("/code-interpreter", response_model=CodeResponse)
def code_interpreter(request: CodeRequest):
    execution_result = execute_python_code(request.code)

    # If no error occurred
    if execution_result["success"]:
        return CodeResponse(
            error=[],
            result=execution_result["output"],
        )

    # If error occurred → extract line from traceback
    error_lines = extract_error_line(execution_result["output"])

    return CodeResponse(
        error=error_lines,
        result=execution_result["output"],
    )