"""Base LLM interface for context-hook."""

import abc

class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass

class LLMProvider(abc.ABC):
    """Abstract base class for all LLM providers."""

    @abc.abstractmethod
    def generate(self, prompt: str, max_retries: int = 3) -> str:
        """Send a prompt to the LLM and return the text response.

        Args:
            prompt: The complete prompt string.
            max_retries: How many times to retry on transient errors (like rate limits).

        Returns:
            The generated text response.

        Raises:
            LLMError: On any API failure or unexpected response.
        """
        pass

def get_provider(config) -> LLMProvider:
    """Factory function to get the configured LLM provider."""
    # We import implementations here to avoid circular imports
    # or failing if a specific provider's SDK is not installed
    
    provider_name = config.provider.lower()
    
    if provider_name == "gemini":
        from context_hook.gemini import GeminiClient, GEMINI_DEFAULT_MODEL
        return GeminiClient(api_key=config.get_api_key(), model=config.model or GEMINI_DEFAULT_MODEL)
    elif provider_name == "openai":
        from context_hook.openai import OpenAIClient, OPENAI_DEFAULT_MODEL
        return OpenAIClient(
            api_key=config.get_api_key(),
            model=config.model or OPENAI_DEFAULT_MODEL,
            base_url=config.base_url,
        )

    raise RuntimeError(f"Unknown or unsupported LLM provider: '{provider_name}'")
