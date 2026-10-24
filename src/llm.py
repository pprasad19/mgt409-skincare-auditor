"""Model construction, and the switch that turns prompt caching on and off.

The cache comparison the report needs comes down to one detail: providers cache
a *prefix*. Two calls share a cached prefix only if their prompts are byte-identical
from the first character up to the cache boundary. So:

  cache on  -> the system prompt is stable across calls, and the second call
               onward reads the shared prefix at the cached rate
  cache off -> a unique nonce is placed at the very front, so no two calls
               share a prefix and every call pays full input price

The nonce has to lead. Putting it at the end would leave the prefix intact and
produce a "cache off" run that quietly still hits the cache — which is exactly
the failure HW6 Problem 4 warns about, and why usage.check_cache_mode() verifies
the outcome from the returned token counts instead of trusting the setting.
"""

from __future__ import annotations

import uuid

from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

from env_file import require
from usage import MODEL

PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# Providers only cache prefixes above a minimum length — commonly around 1024
# tokens. A system prompt shorter than that will never cache no matter how
# stable it is, so a measured "no saving" result may say more about prompt size
# than about caching. preflight.py reports the prompt's token count for exactly
# this reason.
TYPICAL_CACHE_MINIMUM_TOKENS = 1024

# gpt-6-luna rejects function tools on /v1/chat/completions unless reasoning is
# off: "Function tools with reasoning_effort are not supported ... set
# reasoning_effort to 'none'". Both agents carry the trap tools, so both need
# this. The alternative is the /v1/responses endpoint, which would mean trusting
# the gateway to proxy it — not a dependency worth taking on two days out.
#
# Cost note: reasoning tokens are billed at the output rate, so turning them off
# also makes every call cheaper. Measured reasoning use before disabling was
# ~30 tokens per short call.
MODEL_SETTINGS = OpenAIChatModelSettings(openai_reasoning_effort="none")


def build_model(model: str = MODEL) -> OpenAIChatModel:
    client = AsyncOpenAI(base_url=PORTKEY_BASE_URL, api_key=require("PORTKEY_API_KEY"))
    return OpenAIChatModel(model, provider=OpenAIProvider(openai_client=client))


def with_cache_mode(system_prompt: str, cache_enabled: bool) -> str:
    """Return the system prompt, prefixed with a nonce when caching is off."""
    if cache_enabled:
        return system_prompt
    return f"[run-nonce {uuid.uuid4().hex}]\n{system_prompt}"
