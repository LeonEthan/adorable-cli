from pathlib import Path
from typing import Optional

from agno.agent import Agent
from agno.models.openai import OpenAILike
from agno.tools.crawl4ai import Crawl4aiTools
from agno.tools.file import FileTools
from agno.tools.python import PythonTools
from agno.tools.shell import ShellTools
from agno.tools.tavily import TavilyTools

from adorable_cli.tools.vision_tool import create_image_understanding_tool


def create_file_search_agent(
    model_id: str, api_key: Optional[str], base_url: Optional[str]
) -> Agent:
    return Agent(
        name="File Search Agent",
        role="Locate and retrieve relevant local files and datasets.",
        model=OpenAILike(id=model_id, api_key=api_key, base_url=base_url),
        tools=[FileTools(base_dir=Path.cwd(), all=True)],
        instructions=[
            "You are an expert at navigating file systems.",
            "Your goal is to find files that match the user's query or are relevant to the task.",
            "Use `list_files` to explore directories and `read_file` to inspect contents.",
            "When you find relevant files, return their paths and a brief summary of their contents.",
            "Do not modify any files.",
        ],
        markdown=True,
    )


def create_web_search_agent(
    model_id: str, api_key: Optional[str], base_url: Optional[str]
) -> Agent:
    return Agent(
        name="Web Search Agent",
        role="Fetch external information, documentation, or facts from the web.",
        model=OpenAILike(id=model_id, api_key=api_key, base_url=base_url),
        tools=[TavilyTools(), Crawl4aiTools()],
        instructions=[
            "You are an expert web researcher.",
            "Use `tavily_search` to find information and `crawl_url` to read specific pages.",
            "Focus on finding documentation, libraries, or facts relevant to the user's data science goals.",
            "Summarize your findings clearly, citing sources where possible.",
        ],
        markdown=True,
    )


def create_code_writer_agent(
    model_id: str, api_key: Optional[str], base_url: Optional[str]
) -> Agent:
    return Agent(
        name="Code Writing Agent",
        role="Generate high-quality, executable Python code for analysis and modeling.",
        model=OpenAILike(id=model_id, api_key=api_key, base_url=base_url),
        # FileTools allowed to write the code to disk if needed
        tools=[FileTools(base_dir=Path.cwd(), all=True)],
        instructions=[
            "You are a senior Python Data Scientist.",
            "Your task is to write clean, efficient, and well-commented Python code.",
            "Focus on pandas, scikit-learn, matplotlib, and other standard DS libraries.",
            "Do not execute the code yourself; just write it.",
            "You can save the code to a file (e.g., `analysis.py`) using `save_file` if specifically asked, or just return the code block.",
            "Ensure the code handles errors and edge cases.",
        ],
        markdown=True,
    )


def create_code_execution_agent(
    model_id: str, api_key: Optional[str], base_url: Optional[str], confirm_mode: str = "auto"
) -> Agent:
    # This agent needs special handling for confirmation mode
    agent = Agent(
        name="Code Execution Agent",
        role="Safely execute generated code in a controlled environment and capture outputs.",
        model=OpenAILike(id=model_id, api_key=api_key, base_url=base_url),
        tools=[
            PythonTools(base_dir=Path.cwd()),
            ShellTools(base_dir=Path.cwd()),
            create_image_understanding_tool(),  # To understand plots if generated
        ],
        instructions=[
            "You are a careful code executor.",
            "Receive Python code or shell commands and execute them.",
            "Capture standard output and standard error.",
            "If the code generates plots, ensure they are saved to files or displayed appropriately.",
            "Report the execution results faithfully.",
            "If execution fails, report the error details.",
        ],
        markdown=True,
    )

    # Apply confirmation settings logic specifically for this agent
    # We'll reuse the logic from builder.py or main.py, but for now let's just set it here if possible
    # ideally the Orchestrator manages the global confirm mode, but individual tools need the flag
    return agent


def create_documentation_agent(
    model_id: str, api_key: Optional[str], base_url: Optional[str]
) -> Agent:
    return Agent(
        name="Documentation Agent",
        role="Synthesize results into clear, user-friendly reports or summaries.",
        model=OpenAILike(id=model_id, api_key=api_key, base_url=base_url),
        tools=[FileTools(base_dir=Path.cwd(), all=True)],
        instructions=[
            "You are a technical writer and data storyteller.",
            "Take the raw results, code, and insights from other agents.",
            "Synthesize them into a coherent narrative.",
            "You can write the final report to a Markdown file (e.g., `report.md`).",
            "Focus on clarity, insights, and actionable conclusions.",
        ],
        markdown=True,
    )
