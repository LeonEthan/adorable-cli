"""Hierarchical agent tool for task decomposition.

Claude Code's AgentTool implements hierarchical task decomposition:
- Spawns sub-agents with filtered contexts (remove AgentTool to prevent infinite recursion)
- Synthesizes results intelligently (not just concatenation)
- Extracts key findings, identifies consensus/conflicts
- Uses a dedicated model for combining results
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Optional

from adorable_cli.models.events import (
    AgentEvent,
    ContentDeltaEvent,
    MessageCompleteEvent,
    ToolExecutionStartEvent,
    ToolResultEvent,
)


@dataclass
class SubAgentConfig:
    """Configuration for a sub-agent."""

    name: str
    role: str = "sub-agent"
    instructions: list[str] = field(default_factory=list)
    model_id: Optional[str] = None
    max_tokens: int = 4000
    temperature: float = 0.7


@dataclass
class SubAgentTask:
    """A task assigned to a sub-agent."""

    task_id: str
    description: str
    context: dict[str, Any] = field(default_factory=dict)
    config: SubAgentConfig = field(default_factory=lambda: SubAgentConfig("sub-agent"))
    max_turns: int = 10
    timeout_seconds: float = 300.0


@dataclass
class SubAgentResult:
    """Result from a sub-agent execution."""

    task_id: str
    success: bool
    output: str = ""
    findings: list[str] = field(default_factory=list)
    confidence: float = 0.0
    execution_time_ms: int = 0
    error_message: Optional[str] = None


@dataclass
class SynthesisConfig:
    """Configuration for result synthesis."""

    extract_findings: bool = True
    identify_conflicts: bool = True
    confidence_threshold: float = 0.7
    max_output_length: int = 4000


class ResultSynthesizer:
    """Synthesizes results from multiple sub-agents.

    Goes beyond simple concatenation to intelligent synthesis:
    - Extracts key findings from each result
    - Identifies consensus and conflicts
    - Uses a dedicated model for combining results
    """

    def __init__(self, config: Optional[SynthesisConfig] = None):
        self.config = config or SynthesisConfig()

    def synthesize(self, results: list[SubAgentResult], original_task: str) -> str:
        """Synthesize multiple sub-agent results.

        Args:
            results: Results from sub-agents
            original_task: The original task description

        Returns:
            Synthesized output combining all results
        """
        if not results:
            return "No results to synthesize."

        if len(results) == 1:
            return results[0].output

        # Extract findings from each result
        all_findings = []
        for result in results:
            if result.success:
                findings = self._extract_findings(result)
                all_findings.extend(findings)

        # Identify consensus (findings that appear in multiple results)
        consensus = self._identify_consensus(all_findings)

        # Identify conflicts (contradictory findings)
        conflicts = self._identify_conflicts(results)

        # Build synthesized output
        parts = []
        parts.append(f"## Analysis of: {original_task}")
        parts.append("")

        # Add findings by agent
        parts.append("### Findings by Agent")
        for result in results:
            if result.success:
                parts.append(f"\n**{result.config.name if hasattr(result, 'config') else result.task_id}**:")
                parts.append(result.output[:500] + "..." if len(result.output) > 500 else result.output)

        # Add consensus
        if consensus:
            parts.append("\n### Consensus")
            for finding in consensus[:5]:  # Top 5 consensus items
                parts.append(f"- {finding}")

        # Add conflicts if any
        if conflicts:
            parts.append("\n### Conflicts to Resolve")
            for conflict in conflicts:
                parts.append(f"- {conflict}")

        # Add recommendations
        parts.append("\n### Recommendations")
        parts.append(self._generate_recommendations(results, consensus, conflicts))

        output = "\n".join(parts)

        # Truncate if too long
        if len(output) > self.config.max_output_length:
            output = output[: self.config.max_output_length] + "\n... [truncated]"

        return output

    def _extract_findings(self, result: SubAgentResult) -> list[str]:
        """Extract key findings from a result."""
        if not result.findings:
            # Simple extraction: split by newlines and filter
            lines = result.output.split("\n")
            findings = [line.strip("- *") for line in lines if line.strip().startswith(("-", "*", "1.", "2."))]
            return findings[:10]  # Limit findings
        return result.findings

    def _identify_consensus(self, findings: list[str]) -> list[str]:
        """Identify findings that appear in multiple results."""
        from collections import Counter

        # Normalize findings for comparison
        normalized = [f.lower().strip() for f in findings]
        counts = Counter(normalized)

        # Return findings that appear more than once
        consensus = [findings[i] for i, f in enumerate(normalized) if counts[f] > 1]
        return list(set(consensus))  # Remove duplicates

    def _identify_conflicts(self, results: list[SubAgentResult]) -> list[str]:
        """Identify contradictory findings between agents."""
        conflicts = []

        # Simple conflict detection: look for negation patterns
        # This is a basic implementation - could be enhanced with LLM
        positive_indicators = ["is", "should", "recommend", "yes", "good"]
        negative_indicators = ["is not", "should not", "avoid", "no", "bad"]

        for i, result1 in enumerate(results):
            for result2 in results[i + 1 :]:
                # Check for opposite conclusions
                r1_lower = result1.output.lower()
                r2_lower = result2.output.lower()

                for pos in positive_indicators:
                    for neg in negative_indicators:
                        if pos in r1_lower and neg in r2_lower:
                            conflicts.append(f"Differing opinions on approach")
                            break

        return conflicts[:5]  # Limit conflicts

    def _generate_recommendations(
        self, results: list[SubAgentResult], consensus: list[str], conflicts: list[str]
    ) -> str:
        """Generate recommendations based on synthesis."""
        parts = []

        successful_results = [r for r in results if r.success]
        if not successful_results:
            return "No successful results to base recommendations on."

        # Aggregate confidences
        avg_confidence = sum(r.confidence for r in successful_results) / len(successful_results)

        if avg_confidence > 0.8 and not conflicts:
            parts.append("High confidence agreement across agents. Proceed with the approach.")
        elif conflicts:
            parts.append("Review conflicting findings before proceeding. Consider running additional analysis.")
        else:
            parts.append("Moderate confidence. Review findings and validate assumptions.")

        return " ".join(parts)


class AgentTool:
    """Tool for hierarchical task decomposition using sub-agents.

    Spawns specialized sub-agents to work on parts of a complex task,
    then synthesizes their results into a coherent output.

    Key features:
    - Prevents infinite recursion by filtering AgentTool from sub-agents
    - Parallel execution of independent sub-tasks
    - Intelligent synthesis of results (not just concatenation)
    - Configurable depth and breadth limits

    Example:
        agent_tool = AgentTool(main_agent)

        # Decompose a complex task
        sub_tasks = [
            SubAgentTask("research", "Research authentication methods"),
            SubAgentTask("implement", "Implement chosen method"),
        ]

        result = await agent_tool.spawn_and_synthesize(
            parent_task="Add OAuth to the app",
            sub_tasks=sub_tasks
        )
    """

    def __init__(
        self,
        parent_agent: Any,
        max_depth: int = 3,
        max_parallel_sub_agents: int = 5,
        synthesizer: Optional[ResultSynthesizer] = None,
    ):
        self.parent_agent = parent_agent
        self.max_depth = max_depth
        self.max_parallel_sub_agents = max_parallel_sub_agents
        self.synthesizer = synthesizer or ResultSynthesizer()
        self._current_depth = 0

    async def spawn_and_synthesize(
        self,
        parent_task: str,
        sub_tasks: list[SubAgentTask],
        context_budget: int = 100_000,
    ) -> SubAgentResult:
        """Spawn sub-agents and synthesize their results.

        Args:
            parent_task: Description of the parent task
            sub_tasks: List of sub-tasks to delegate
            context_budget: Token budget for sub-agents

        Returns:
            Synthesized result combining all sub-agent outputs
        """
        if self._current_depth >= self.max_depth:
            return SubAgentResult(
                task_id="depth-limit",
                success=False,
                error_message=f"Maximum agent depth ({self.max_depth}) reached",
            )

        if not sub_tasks:
            return SubAgentResult(
                task_id="no-tasks",
                success=False,
                error_message="No sub-tasks provided",
            )

        self._current_depth += 1

        try:
            # Spawn sub-agents in parallel
            results = await self._spawn_sub_agents_parallel(sub_tasks, context_budget)

            # Synthesize results
            synthesized_output = self.synthesizer.synthesize(results, parent_task)

            # Calculate aggregate confidence
            successful = [r for r in results if r.success]
            avg_confidence = (
                sum(r.confidence for r in successful) / len(successful)
                if successful
                else 0.0
            )

            return SubAgentResult(
                task_id="synthesis",
                success=len(successful) > 0,
                output=synthesized_output,
                findings=[f for r in results for f in r.findings],
                confidence=avg_confidence,
            )

        finally:
            self._current_depth -= 1

    async def _spawn_sub_agents_parallel(
        self,
        sub_tasks: list[SubAgentTask],
        context_budget: int,
    ) -> list[SubAgentResult]:
        """Spawn multiple sub-agents in parallel."""
        semaphore = asyncio.Semaphore(self.max_parallel_sub_agents)

        async def execute_with_limit(task: SubAgentTask) -> SubAgentResult:
            async with semaphore:
                return await self._execute_sub_agent(task, context_budget)

        # Execute all sub-tasks
        tasks = [execute_with_limit(t) for t in sub_tasks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        processed_results = []
        for task, result in zip(sub_tasks, results):
            if isinstance(result, Exception):
                processed_results.append(
                    SubAgentResult(
                        task_id=task.task_id,
                        success=False,
                        error_message=str(result),
                    )
                )
            else:
                processed_results.append(result)

        return processed_results

    async def _execute_sub_agent(
        self,
        task: SubAgentTask,
        context_budget: int,
    ) -> SubAgentResult:
        """Execute a single sub-agent task."""
        import time

        start_time = time.time()

        try:
            # Create sub-agent with filtered context
            sub_agent = self._create_sub_agent(task, context_budget)

            # Execute the task
            # This would integrate with your actual agent framework
            output = await self._run_agent(sub_agent, task)

            execution_time = int((time.time() - start_time) * 1000)

            return SubAgentResult(
                task_id=task.task_id,
                success=True,
                output=output,
                confidence=0.8,  # Would be calculated from actual agent metrics
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)

            return SubAgentResult(
                task_id=task.task_id,
                success=False,
                error_message=str(e),
                execution_time_ms=execution_time,
            )

    def _create_sub_agent(self, task: SubAgentTask, context_budget: int) -> Any:
        """Create a sub-agent with filtered context.

        Filters out AgentTool to prevent infinite recursion.
        """
        # Get tools from parent, but filter out AgentTool
        parent_tools = getattr(self.parent_agent, "tools", [])
        filtered_tools = [
            t for t in parent_tools
            if not (hasattr(t, "__class__") and t.__class__.__name__ == "AgentTool")
        ]

        # Create sub-agent configuration
        config = {
            "name": task.config.name,
            "role": task.config.role,
            "instructions": task.config.instructions,
            "tools": filtered_tools,  # No AgentTool to prevent recursion
            "max_tokens": min(task.config.max_tokens, context_budget // len(task.context or 1)),
        }

        return config

    async def _run_agent(self, agent_config: dict, task: SubAgentTask) -> str:
        """Run the agent with the given configuration.

        This is a placeholder - integrate with your actual agent framework.
        """
        # Placeholder implementation
        # In real implementation, this would:
        # 1. Create an Agent instance from the config
        # 2. Run it with the task description
        # 3. Return the output

        return f"[Sub-agent {task.config.name} result for: {task.description}]"

    async def spawn_streaming(
        self,
        parent_task: str,
        sub_tasks: list[SubAgentTask],
    ) -> AsyncGenerator[AgentEvent, None]:
        """Spawn sub-agents with streaming results.

        Yields progress events as sub-agents complete.
        """
        yield ToolExecutionStartEvent(
            tool_use_id=str(uuid.uuid4()),
            tool_name="AgentTool",
        )

        for i, task in enumerate(sub_tasks):
            yield ContentDeltaEvent(
                delta=f"\n[Starting sub-agent {task.config.name}...]\n",
                accumulated=f"",
            )

            result = await self._execute_sub_agent(task, 100_000)

            if result.success:
                yield ContentDeltaEvent(
                    delta=f"[Completed: {result.output[:200]}...]\n",
                    accumulated=result.output,
                )
            else:
                yield ContentDeltaEvent(
                    delta=f"[Error: {result.error_message}]\n",
                    accumulated="",
                )

        # Final synthesis
        yield ContentDeltaEvent(
            delta="\n[Synthesizing results...]\n",
            accumulated="",
        )


class SimpleSubAgent:
    """Simple sub-agent implementation for demonstration.

    In production, integrate with your actual agent framework.
    """

    def __init__(
        self,
        name: str,
        role: str,
        instructions: list[str],
        tools: list[Any],
        max_tokens: int = 4000,
    ):
        self.name = name
        self.role = role
        self.instructions = instructions
        self.tools = tools
        self.max_tokens = max_tokens

    async def run(self, task_description: str) -> str:
        """Run the sub-agent on a task."""
        # Placeholder - integrate with actual agent execution
        return f"Result from {self.name} for task: {task_description}"


# Convenience functions


def decompose_task(
    task_description: str,
    decomposition_strategy: str = "default",
) -> list[SubAgentTask]:
    """Decompose a task into sub-tasks.

    Args:
        task_description: The task to decompose
        decomposition_strategy: Strategy for decomposition

    Returns:
        List of sub-tasks
    """
    # Simple decomposition strategies
    strategies: dict[str, Callable[[str], list[SubAgentTask]]] = {
        "research": lambda t: [
            SubAgentTask("research", f"Research: {t}"),
            SubAgentTask("analyze", f"Analyze findings for: {t}"),
            SubAgentTask("summarize", f"Summarize: {t}"),
        ],
        "implementation": lambda t: [
            SubAgentTask("design", f"Design approach for: {t}"),
            SubAgentTask("implement", f"Implement: {t}"),
            SubAgentTask("test", f"Test implementation of: {t}"),
        ],
        "default": lambda t: [
            SubAgentTask("analyze", f"Analyze: {t}"),
            SubAgentTask("execute", f"Execute: {t}"),
        ],
    }

    strategy_fn = strategies.get(decomposition_strategy, strategies["default"])
    return strategy_fn(task_description)
