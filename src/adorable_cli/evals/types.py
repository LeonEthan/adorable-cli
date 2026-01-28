from typing import List, Optional
from pydantic import BaseModel

class EvalCase(BaseModel):
    input: str
    expected: Optional[str] = None
    expected_contains: Optional[str] = None
    description: Optional[str] = None

class EvalSuite(BaseModel):
    name: str
    description: Optional[str] = None
    cases: List[EvalCase]

class EvalResult(BaseModel):
    case: EvalCase
    actual_output: str
    success: bool
    error: Optional[str] = None

class EvalReport(BaseModel):
    suite_name: str
    results: List[EvalResult]
    total: int
    passed: int
    failed: int
