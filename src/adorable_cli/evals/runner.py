import asyncio
import yaml
from pathlib import Path
from typing import List

from adorable_cli.evals.types import EvalSuite, EvalResult, EvalReport
from adorable_cli.agent.builder import build_component

class EvalRunner:
    def __init__(self):
        pass

    def load_suite(self, path: Path) -> EvalSuite:
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return EvalSuite(**data)

    async def run_case(self, agent, case) -> EvalResult:
        try:
            # We use the agent to generate a response
            # Assuming agent.run() or similar exists and returns a response object
            # or we use interactive run loop logic.
            # But here we want a single turn response.
            
            # Agno agents usually have .run() or .print_response()
            # .run() returns a generator or a response object depending on stream=True
            
            response = await agent.arun(case.input)
            
            # The response object from Agno usually has .content or similar
            # Let's check Agno agent structure if possible, but assuming .content is safe
            actual = response.content if hasattr(response, "content") else str(response)

            success = True
            if case.expected and case.expected != actual:
                success = False
            if case.expected_contains and case.expected_contains not in actual:
                success = False
            
            return EvalResult(
                case=case,
                actual_output=actual,
                success=success
            )
        except Exception as e:
            return EvalResult(
                case=case,
                actual_output="",
                success=False,
                error=str(e)
            )

    async def run_suite(self, suite: EvalSuite, team: str = None) -> EvalReport:
        # Build a fresh component for the suite (or per case if needed, but suite level is better)
        component = build_component(team=team)
        
        results = []
        for case in suite.cases:
            result = await self.run_case(component, case)
            results.append(result)
        
        passed = sum(1 for r in results if r.success)
        failed = len(results) - passed
        
        return EvalReport(
            suite_name=suite.name,
            results=results,
            total=len(results),
            passed=passed,
            failed=failed
        )
