"""
llm_client -- shared OpenAI/OpenRouter client with retry-on-empty-response.
Testing showed this is genuinely random, intermittent provider-side flakiness --
NOT correlated with call position, prompt length, or sequence timing (tested
and ruled out each of these directly). The only real mitigation is enough
retries that the combined failure probability becomes negligible.
"""
import os
import time
from openai import OpenAI
MAX_RETRIES = 5
PRE_CALL_DELAY_SECONDS = 0.3  # small, harmless precaution -- not proven to fix anything
def get_llm_client() -> OpenAI:
    return OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
    )
def safe_completion(client: OpenAI, **kwargs) -> str:
    """
    Calls client.chat.completions.create(**kwargs) and returns the content string.
    Retries up to MAX_RETRIES times if content comes back None -- this is the
    real defense, since the failure is random and not preventable from our side.
    """
    time.sleep(PRE_CALL_DELAY_SECONDS)
    last_error = None
    for attempt in range(MAX_RETRIES):
        response = client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        if content is not None:
            return content.strip()
        last_error = f"attempt {attempt + 1}/{MAX_RETRIES}: content was None"
        if attempt < MAX_RETRIES - 1:
            time.sleep(1.0)
    raise RuntimeError(f"LLM returned empty content {MAX_RETRIES} times in a row. Last: {last_error}")
