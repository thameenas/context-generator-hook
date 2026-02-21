"""Gemini API client for context-hook."""

from google import genai


class GeminiError(Exception):
    """Raised when a Gemini API call fails."""
    pass


class GeminiClient:
    """Wrapper around the Google GenAI SDK for Gemini API calls."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate(self, prompt: str) -> str:
        """Send a prompt to Gemini and return the text response.

        Args:
            prompt: The complete prompt string.

        Returns:
            The generated text response.

        Raises:
            GeminiError: On any API failure (network, rate limit, etc.)
        """
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            if response.text is None:
                raise GeminiError("Gemini returned an empty response")
            return response.text.strip()
        except GeminiError:
            raise
        except Exception as e:
            raise GeminiError(f"Gemini API call failed: {e}") from e
