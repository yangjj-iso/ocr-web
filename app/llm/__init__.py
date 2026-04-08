"""
LLM 抽象层 — 支持多 Provider 的统一接口

使用方式:
    from app.llm import get_llm_client
    client = get_llm_client()
    result = await client.chat_completion(messages=[...])
"""
from app.llm.client import get_llm_client  # noqa: F401
