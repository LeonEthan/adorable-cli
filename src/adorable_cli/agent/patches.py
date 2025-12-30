from typing import Any, Dict, Optional
from agno.tools.function import Function, FunctionCall
import agno.utils.tools
import agno.models.base
import agno.models.openai.chat
from agno.utils.log import logger
import json

# Store original function to avoid recursion if patched multiple times
_original_get_function_call_for_tool_call = agno.utils.tools.get_function_call_for_tool_call
_original_parse_provider_response = agno.models.openai.chat.OpenAIChat._parse_provider_response

def safe_get_function_call_for_tool_call(
    tool_call: Dict[str, Any], functions: Optional[Dict[str, Function]] = None
) -> Optional[FunctionCall]:
    """
    Monkey patch for agno.utils.tools.get_function_call_for_tool_call.
    
    1. Intercepts missing functions and returns a dummy function that produces an error message.
    2. Sanitizes malformed JSON arguments to prevent 'invalid arguments' errors from API.
    """
    
    # Pre-sanitize arguments if they look suspicious (e.g. double JSON)
    if tool_call.get("type") == "function":
        _function_data = tool_call.get("function", {})
        _args_str = _function_data.get("arguments", "")
        
        # Check for concatenated JSONs (e.g. "{...}{...}")
        if _args_str.count("}{") > 0:
            logger.warning("Monkey Patch: Detected malformed arguments (concatenated JSON). Sanitizing...")
            # Try to keep the first valid JSON object
            try:
                # Find the first closing brace that matches the first opening brace
                # Simple heuristic: split by "}{" and take the first part + "}"
                # This is not perfect but covers the common case "{...}{...}"
                _sanitized = _args_str.split("}{")[0] + "}"
                # Validate if it parses
                json.loads(_sanitized)
                _function_data["arguments"] = _sanitized
                logger.info(f"Monkey Patch: Sanitized arguments to: {_sanitized}")
            except Exception:
                # Fallback to empty dict if repair fails
                _function_data["arguments"] = "{}"
                logger.warning("Monkey Patch: Failed to repair arguments. Reset to '{}'.")

    result = _original_get_function_call_for_tool_call(tool_call, functions)
    
    if result is None and tool_call.get("type") == "function":
        _tool_call_id = tool_call.get("id")
        _function_data = tool_call.get("function", {})
        _function_name = _function_data.get("name")
        
        if _tool_call_id and _function_name:
            logger.warning(f"Monkey Patch: Intercepted missing function '{_function_name}'. Generating error response.")
            
            # Create a dummy function that returns the error message
            def error_handler(*args, **kwargs):
                return f"Error: Function {_function_name} not found. Please check the tool name and try again."
            
            # Create a dummy function object
            # We must ensure show_result is True so it gets returned to the model
            dummy_func = Function(
                name=_function_name, 
                entrypoint=error_handler,
                show_result=True
            )
            
            # Return a valid FunctionCall
            return FunctionCall(function=dummy_func, arguments={}, call_id=_tool_call_id)
            
    return result

def safe_parse_provider_response(self, response, response_format=None):
    """
    Monkey patch for OpenAIChat._parse_provider_response.
    
    Sanitizes tool call arguments in the response object BEFORE it is converted to ModelResponse.
    This ensures that the 'assistant' message stored in history contains valid JSON arguments,
    preventing 500 errors from the API in subsequent turns.
    """
    try:
        response_message = response.choices[0].message
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                if tool_call.function and tool_call.function.arguments:
                    args = tool_call.function.arguments
                    # Check for malformed JSON (concatenated objects)
                    if "}{" in args:
                        logger.warning(f"Monkey Patch: Detected malformed tool arguments in provider response: {args[:50]}...")
                        try:
                            # Attempt repair: take first JSON object
                            sanitized = args.split("}{")[0] + "}"
                            json.loads(sanitized) # Verify validity
                            tool_call.function.arguments = sanitized
                            logger.info("Monkey Patch: Repaired tool arguments in provider response.")
                        except Exception:
                            # Fallback: empty JSON
                            tool_call.function.arguments = "{}"
                            logger.warning("Monkey Patch: Could not repair tool arguments. Replaced with empty JSON.")
    except Exception as e:
        logger.error(f"Monkey Patch: Error processing provider response for sanitization: {e}")

    # Call original method
    return _original_parse_provider_response(self, response, response_format)

def apply_patches():
    """Apply monkey patches to agno library."""
    # Patch 1: Robust function lookup (execution phase)
    agno.utils.tools.get_function_call_for_tool_call = safe_get_function_call_for_tool_call
    # Also patch where it's imported
    agno.models.base.get_function_call_for_tool_call = safe_get_function_call_for_tool_call
    
    # Patch 2: Response parsing (history storage phase)
    # We patch the class method directly
    agno.models.openai.chat.OpenAIChat._parse_provider_response = safe_parse_provider_response
    
    logger.info("Applied monkey patches for robust tool execution and history sanitization.")
