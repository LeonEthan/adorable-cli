from pathlib import Path
from typing import Optional

from agno.agent import Agent
from agno.media import Image
from agno.models.openai import OpenAILike
from agno.tools import Toolkit
from agno.utils.log import logger

from adorable_cli.settings import settings
from adorable_cli.agent.prompts import VLM_AGENT_DESCRIPTION, VLM_AGENT_INSTRUCTIONS


class ImageUnderstandingTool(Toolkit):
    def __init__(self, **kwargs):
        super().__init__(
            name="image_understanding_tool",
            tools=[self.analyze_image],
            **kwargs
        )
        
        # Determine VLM model ID
        self.vlm_model_id = settings.vlm_model_id or settings.model_id
        
        # Create dedicated VLM Agent
        self.vlm_agent = Agent(
            name="vlm-agent",
            model=OpenAILike(
                id=self.vlm_model_id,
                api_key=settings.api_key,
                base_url=settings.base_url,
                max_tokens=4096,
            ),
            description=VLM_AGENT_DESCRIPTION,
            instructions=VLM_AGENT_INSTRUCTIONS,
            add_datetime_to_context=True,
            markdown=True,
            # Disable unnecessary features to optimize performance
            enable_agentic_state=False,
            add_history_to_context=False,
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
            logger.error(f"Error analyzing image: {e}")
            return f"Error analyzing image: {str(e)}"


def create_image_understanding_tool() -> ImageUnderstandingTool:
    """
    Create an image understanding tool that wraps the VLM Agent.
    """
    return ImageUnderstandingTool()
