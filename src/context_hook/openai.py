"""OpenAI-compatible API client for context-hook (supports OpenAI and OpenRouter)."""

import time
import openai as openai_lib
from context_hook.llm import LLMProvider, LLMError

OPENAI_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIError(LLMError):
    pass


class OpenAIClient(LLMProvider):
    def __init__(self, api_key: str, model: str = OPENAI_DEFAULT_MODEL, base_url: str | None = None):
        self.model = model
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = openai_lib.OpenAI(**kwargs)

    def generate(self, prompt: str, max_retries: int = 3) -> str:
        retries = 0
        base_delay = 15

        while True:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                )
                result = response.choices[0].message.content
                if result is None:
                    raise OpenAIError("OpenAI-compatible API returned an empty response")
                # Strip markdown code block wrappers if present (matches gemini.py behaviour)
                result = result.strip()
                if result.startswith("```markdown"):
                    result = result[len("```markdown"):].strip()
                elif result.startswith("```"):
                    result = result[3:].strip()
                if result.endswith("```"):
                    result = result[:-3].strip()
                return result

            except openai_lib.RateLimitError as e:
                if retries < max_retries:
                    retries += 1
                    delay = base_delay * (2 ** (retries - 1))
                    print(f"Rate limited (429). Retrying in {delay}s (Attempt {retries}/{max_retries})...", flush=True)
                    time.sleep(delay)
                    continue
                raise OpenAIError(f"API call failed: {e}") from e
            except openai_lib.APIError as e:
                raise OpenAIError(f"API call failed: {e}") from e
            except Exception as e:
                raise OpenAIError(f"API call failed: {e}") from e
