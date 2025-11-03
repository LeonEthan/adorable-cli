import os
from pathlib import Path
from typing import Optional

from agno.agent import Agent
from agno.media import Image
from agno.models.openai import OpenAILike
from agno.tools import Toolkit
from adorable_cli.hooks.context_guard import (
    ensure_context_within_window,
    restore_context_settings,
)


class ImageUnderstandingTool(Toolkit):
    def __init__(self, **kwargs):
        super().__init__(
            name="image_understanding_tool",
            tools=[self.analyze_image],
            **kwargs
        )
        
        # Read VLM model ID, support independent configuration
        self.vlm_model_id = os.environ.get(
            "ADORABLE_VLM_MODEL_ID",
            os.environ.get("ADORABLE_MODEL_ID", "gpt-5-mini"))
        
        # Create dedicated VLM Agent
        self.vlm_agent = Agent(
            name="vlm-agent",
            model=OpenAILike(
                id=self.vlm_model_id,
                api_key=os.environ.get("OPENAI_API_KEY") or os.environ.get("API_KEY"),
                base_url=os.environ.get("OPENAI_BASE_URL") or os.environ.get("BASE_URL"),
                max_tokens=4096,
            ),
            description="A specialized agent for understanding images and visual content.",
            instructions=[
                "You are an expert in image analysis and visual understanding.",
                "Analyze the provided image and provide a detailed, accurate description.",
                "Focus on objects, scenes, text (if any), colors, composition, and context.",
                "If asked a question about the image, answer precisely based on visual evidence."
            ],
            add_datetime_to_context=True,
            markdown=True,
            # Disable unnecessary features to optimize performance
            enable_agentic_state=False,
            add_history_to_context=False,
            # Context guard hooks (protect smaller VLM window)
            pre_hooks=[ensure_context_within_window],
            post_hooks=[restore_context_settings],
        )

    def analyze_image(self, image_path: str, query: Optional[str] = None) -> str:
        """
        Analyze the specified image file.
        
        Args:
            image_path: Path to the image file
            query: Analysis instruction (e.g., 'Describe this image', 'What is written here?')
        
        Returns:
            Text result of image analysis
        """
        path = Path(image_path).expanduser()
        
        # Validate file
        if not path.exists():
            return f"Error: Image file not found at {path}"
        
        if path.suffix.lower() not in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
            return f"Error: Unsupported image format: {path.suffix}. Supported: .jpg, .png, .webp"
        
        try:
            # Prepare input prompt
            prompt = query or "Please describe this image in detail."
            
            # Call VLM Agent
            response = self.vlm_agent.run(
                prompt,
                images=[Image(filepath=str(path))],
                stream=False  # No streaming needed for internal tool calls
            )
            
            return response.content if response.content else "No response received from image analysis."
            
        except Exception as e:
            return f"Error analyzing image: {str(e)}"


def create_image_understanding_tool() -> ImageUnderstandingTool:
    """
    Create an image understanding tool that wraps the VLM Agent.
    Model can be specified via ADORABLE_VLM_MODEL_ID environment variable.
    """
    return ImageUnderstandingTool()