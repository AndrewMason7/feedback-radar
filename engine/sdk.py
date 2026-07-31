"""
Google Antigravity SDK agent configuration, retry policies, and error recovery hooks.
"""
import os


def build_retry_policy():
    """RetryConfig from SDK v0.1.9 — automatic retries for transient API errors."""
    try:
        from google.antigravity import (
            RetryConfig, ModelAPIRetryConfig, ModelOutputRetryConfig)
        return RetryConfig(
            api_retry=ModelAPIRetryConfig(
                max_retries=3,
                initial_sleep_duration_ms=200,
                exponential_multiplier=2.0,
            ),
            model_output_retry=ModelOutputRetryConfig(max_retries=2),
        )
    except (ImportError, TypeError, AttributeError):
        print("[info] RetryConfig needs SDK v0.1.9+ — continuing without retries")
        return None


def build_tool_error_hook():
    """Structured tool exception handling from SDK v0.1.9."""
    try:
        from google.antigravity import hooks, ToolExecutionError

        @hooks.on_tool_error
        async def handle_tool_error(data):
            if isinstance(data, ToolExecutionError):
                print("[warn] tool '%s' failed — telling the agent to recover" % data.tool_name)
                return ("[Recovered from a tool error in '%s'. Continue with data available.]" % data.tool_name)
            return None
        return handle_tool_error
    except (ImportError, TypeError, AttributeError):
        print("[info] ToolExecutionError hooks need SDK v0.1.9+ — continuing without them")
        return None


def agent_config(system_instructions, response_schema=None, api_key=None):
    """Shared LocalAgentConfig: system prompt + v0.1.9 retry policy + error hook."""
    cfg = {"system_instructions": system_instructions}
    model = os.getenv("RADAR_MODEL", "")
    if model:
        cfg["model"] = model
    if response_schema is not None:
        cfg["response_schema"] = response_schema
    if api_key:
        cfg["api_key"] = api_key
    retry = build_retry_policy()
    if retry is not None:
        cfg["retry_config"] = retry
    hook = build_tool_error_hook()
    if hook is not None:
        cfg["hooks"] = [hook]
    return cfg
