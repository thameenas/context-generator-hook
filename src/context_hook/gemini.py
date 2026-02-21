"""Gemini API client for context-hook."""

import time
from google import genai
from google.genai.errors import APIError


class GeminiError(Exception):
    """Raised when a Gemini API call fails."""
    pass


class GeminiClient:
    """Wrapper around the Google GenAI SDK for Gemini API calls."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate(self, prompt: str, max_retries: int = 3) -> str:
        """Send a prompt to Gemini and return the text response.

        Args:
            prompt: The complete prompt string.
            max_retries: How many times to retry on 429 rate limit errors.

        Returns:
            The generated text response.

        Raises:
            GeminiError: On any API failure (network, rate limit, etc.)
        """
        retries = 0
        base_delay = 15  # seconds

        while True:
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                )
                if response.text is None:
                    raise GeminiError("Gemini returned an empty response")
                
                # Clean up markdown code block wrappers if the LLM added them
                result = response.text.strip()
                if result.startswith("```markdown"):
                    result = result[len("```markdown"):].strip()
                elif result.startswith("```"):
                    result = result[3:].strip()
                if result.endswith("```"):
                    result = result[:-3].strip()
                    
                return result
                
            except APIError as e:
                # 429 is Resource Exhausted (Rate Limit)
                if e.code == 429 and retries < max_retries:
                    retries += 1
                    # Exponential backoff: 15s, 30s, 60s
                    delay = base_delay * (2 ** (retries - 1))
                    time.sleep(delay)
                    continue
                raise GeminiError(f"Gemini API call failed: {e}") from e
                
            except Exception as e:
                raise GeminiError(f"Gemini API call failed: {e}") from e
