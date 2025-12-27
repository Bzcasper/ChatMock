from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List

from flask import Blueprint, Response, current_app, jsonify, make_response, request

# Configure production logging
logger = logging.getLogger(__name__)

from .config import BASE_INSTRUCTIONS, GPT5_CODEX_INSTRUCTIONS
from .limits import record_rate_limits_from_response
from .http import build_cors_headers
from .production import RateLimiter
from .reasoning import (
    allowed_efforts_for_model,
    apply_reasoning_to_message,
    build_reasoning_param,
    extract_reasoning_from_model_name,
)
from .upstream import normalize_model_name, start_upstream_request
from .utils import (
    convert_chat_messages_to_responses_input,
    convert_tools_chat_to_responses,
    sse_translate_chat,
    sse_translate_text,
)


openai_bp = Blueprint("openai", __name__)

# Initialize rate limiter (100 requests per 60 seconds)
_rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

# Valid model definitions
_MODEL_GROUPS = [
    ("gpt-5", ["high", "medium", "low", "minimal"]),
    ("gpt-5.1", ["high", "medium", "low"]),
    ("gpt-5.2", ["xhigh", "high", "medium", "low"]),
    ("gpt-5-codex", ["high", "medium", "low"]),
    ("gpt-5.2-codex", ["xhigh", "high", "medium", "low"]),
    ("gpt-5.1-codex", ["high", "medium", "low"]),
    ("gpt-5.1-codex-max", ["xhigh", "high", "medium", "low"]),
    ("gpt-5.1-codex-mini", []),
    ("codex-mini", []),
]


def _get_valid_model_ids(expose_variants: bool = False) -> set[str]:
    """Get set of valid model IDs."""
    model_ids: set[str] = set()
    for base, efforts in _MODEL_GROUPS:
        model_ids.add(base)
        if expose_variants:
            model_ids.update([f"{base}-{effort}" for effort in efforts])
    return model_ids


def _validate_model_id(model_id: str | None, expose_variants: bool = False) -> bool:
    """Check if a model ID is valid."""
    if not model_id or not isinstance(model_id, str):
        return False
    valid_ids = _get_valid_model_ids(expose_variants)
    return model_id in valid_ids


def _log_json(prefix: str, payload: Any) -> None:
    try:
        print(f"{prefix}\n{json.dumps(payload, indent=2, ensure_ascii=False)}")
    except Exception:
        try:
            print(f"{prefix}\n{payload}")
        except Exception:
            pass


def _wrap_stream_logging(label: str, iterator, enabled: bool):
    if not enabled:
        return iterator

    def _gen():
        for chunk in iterator:
            try:
                text = (
                    chunk.decode("utf-8", errors="replace")
                    if isinstance(chunk, (bytes, bytearray))
                    else str(chunk)
                )
                print(f"{label}\n{text}")
            except Exception:
                pass
            yield chunk

    return _gen()


def _get_specialized_instructions(content_type: str | None) -> str | None:
    """Get specialized instructions for content-type specific requests."""
    if not isinstance(content_type, str) or not content_type.strip():
        return None

    content_type = content_type.strip().lower()
    prompts = current_app.config.get("CONTENT_TYPE_PROMPTS", {})
    result = prompts.get(content_type)

    # Debug logging
    verbose = bool(current_app.config.get("VERBOSE"))
    if verbose:
        print(f"DEBUG: Looking for content_type '{content_type}'")
        print(f"DEBUG: Available content types: {list(prompts.keys())}")
        print(f"DEBUG: Found specialized prompt: {bool(result)}")

    return result


def _merge_instructions(base: str, specialized: str | None) -> str:
    """Merge base instructions with specialized content-type instructions."""
    if not specialized:
        return base

    return f"{base}\n\n## SPECIALIZED INSTRUCTIONS FOR {specialized.split()[0].upper()}:\n\n{specialized}"


def _instructions_for_model(model: str, content_type: str | None = None) -> str:
    base = current_app.config.get("BASE_INSTRUCTIONS", BASE_INSTRUCTIONS)
    if model.startswith("gpt-5-codex") or model.startswith("gpt-5.1-codex") or model.startswith("gpt-5.2-codex"):
        codex = current_app.config.get("GPT5_CODEX_INSTRUCTIONS") or GPT5_CODEX_INSTRUCTIONS
        if isinstance(codex, str) and codex.strip():
            base = codex

    # Note: Specialized instructions injected via message prefix (Option C)
    # Instead of merging into instructions parameter (which has strict API limits),
    # specialized content is injected as an initial message to the model.
    # This avoids the "Upstream error" from oversized instruction payloads.

    return base


def _get_specialized_context_message(content_type: str | None) -> dict | None:
    """Create a context message for specialized content types via message injection.

    This implements Option C: Dynamic Instruction Injection.
    Specialized prompts are injected as message content rather than merged into
    the instructions parameter, avoiding OpenAI Responses API size validation limits.

    Returns None if content_type is invalid or not found.
    Logs errors for production debugging.
    """
    try:
        if not isinstance(content_type, str) or not content_type.strip():
            return None

        content_type_normalized = content_type.strip().lower()

        # Validate content_type format (alphanumeric + underscore only)
        if not all(c.isalnum() or c == '_' for c in content_type_normalized):
            logger.warning(f"Invalid content_type format: {content_type}")
            return None

        prompts = current_app.config.get("CONTENT_TYPE_PROMPTS", {})
        if not isinstance(prompts, dict):
            logger.error("CONTENT_TYPE_PROMPTS config is not a dictionary")
            return None

        specialized = prompts.get(content_type_normalized)

        if not specialized:
            verbose = bool(current_app.config.get("VERBOSE"))
            if verbose:
                logger.debug(f"Specialized prompt not found for content_type: {content_type_normalized}")
            return None

        # Validate specialized prompt content
        if not isinstance(specialized, str) or not specialized.strip():
            logger.warning(f"Specialized prompt for '{content_type_normalized}' is empty or invalid")
            return None

        # Check prompt size doesn't exceed reasonable limits (message content has higher limits)
        prompt_size = len(specialized.encode('utf-8'))
        max_prompt_size = 100 * 1024  # 100KB limit for safety
        if prompt_size > max_prompt_size:
            logger.error(f"Specialized prompt '{content_type_normalized}' exceeds size limit: {prompt_size} > {max_prompt_size}")
            return None

        verbose = bool(current_app.config.get("VERBOSE"))
        if verbose:
            logger.info(f"Injecting specialized prompt for '{content_type_normalized}' ({prompt_size} bytes)")

        # Create a message that injects the specialized prompt content
        # The model will see this as an explicit instruction about how to behave
        # Escape special XML characters to prevent injection attacks
        import html
        escaped_prompt = html.escape(specialized, quote=True)

        context_text = f"""<specialized_mode type="{content_type_normalized}">
{escaped_prompt}
</specialized_mode>

Please acknowledge you are now operating in {content_type_normalized} mode and apply these specialized guidelines to all subsequent responses in this conversation."""

        return {
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": context_text
                }
            ]
        }

    except Exception as e:
        logger.exception(f"Error in _get_specialized_context_message: {str(e)}")
        return None


@openai_bp.route("/v1/chat/completions", methods=["POST"])
def chat_completions() -> Response:
    # Check rate limit
    if not _rate_limiter.is_allowed():
        retry_after = _rate_limiter.get_retry_after()
        err = {"error": {"message": "Rate limit exceeded"}}
        resp = jsonify(err)
        resp.status_code = 429
        resp.headers["Retry-After"] = str(retry_after)
        return resp

    verbose = bool(current_app.config.get("VERBOSE"))
    verbose_obfuscation = bool(current_app.config.get("VERBOSE_OBFUSCATION"))
    reasoning_effort = current_app.config.get("REASONING_EFFORT", "medium")
    reasoning_summary = current_app.config.get("REASONING_SUMMARY", "auto")
    reasoning_compat = current_app.config.get("REASONING_COMPAT", "think-tags")
    debug_model = current_app.config.get("DEBUG_MODEL")
    content_type = request.headers.get("X-Prompt-Type", "").strip().lower() or None

    raw = request.get_data(cache=True, as_text=True) or ""
    if verbose:
        try:
            print("IN POST /v1/chat/completions\n" + raw)
        except Exception:
            pass
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        try:
            payload = json.loads(raw.replace("\r", "").replace("\n", ""))
        except Exception:
            err = {"error": {"message": "Invalid JSON body"}}
            if verbose:
                _log_json("OUT POST /v1/chat/completions", err)
            return jsonify(err), 400

    requested_model = payload.get("model")
    model = normalize_model_name(requested_model, debug_model)

    # Validate model ID
    expose_variants = bool(current_app.config.get("EXPOSE_REASONING_MODELS"))
    if not _validate_model_id(requested_model, expose_variants):
        err = {"error": {"message": f"Model '{requested_model}' not found"}}
        if verbose:
            _log_json("OUT POST /v1/chat/completions", err)
        return jsonify(err), 404

    messages = payload.get("messages")
    if messages is None and isinstance(payload.get("prompt"), str):
        messages = [{"role": "user", "content": payload.get("prompt") or ""}]
    if messages is None and isinstance(payload.get("input"), str):
        messages = [{"role": "user", "content": payload.get("input") or ""}]
    if messages is None:
        messages = []
    if not isinstance(messages, list):
        err = {"error": {"message": "Request must include messages: []"}}
        if verbose:
            _log_json("OUT POST /v1/chat/completions", err)
        return jsonify(err), 400

    if isinstance(messages, list):
        sys_idx = next((i for i, m in enumerate(messages) if isinstance(m, dict) and m.get("role") == "system"), None)
        if isinstance(sys_idx, int) and 0 <= sys_idx < len(messages):
            sys_msg = messages.pop(sys_idx)
            if isinstance(sys_msg, dict) and "content" in sys_msg:
                content = sys_msg["content"]
                if isinstance(content, str):
                    messages.insert(0, {"role": "user", "content": content})
    is_stream = bool(payload.get("stream"))
    stream_options = payload.get("stream_options") if isinstance(payload.get("stream_options"), dict) else {}
    include_usage = bool(stream_options.get("include_usage", False))

    tools_responses = convert_tools_chat_to_responses(payload.get("tools"))
    tool_choice = payload.get("tool_choice", "auto")
    parallel_tool_calls = bool(payload.get("parallel_tool_calls", False))
    responses_tools_payload = payload.get("responses_tools") if isinstance(payload.get("responses_tools"), list) else []
    extra_tools: List[Dict[str, Any]] = []
    had_responses_tools = False
    if isinstance(responses_tools_payload, list):
        for _t in responses_tools_payload:
            if not (isinstance(_t, dict) and isinstance(_t.get("type"), str)):
                continue
            if _t.get("type") not in ("web_search", "web_search_preview"):
                err = {
                    "error": {
                        "message": "Only web_search/web_search_preview are supported in responses_tools",
                        "code": "RESPONSES_TOOL_UNSUPPORTED",
                    }
                }
                if verbose:
                    _log_json("OUT POST /v1/chat/completions", err)
                return jsonify(err), 400
            extra_tools.append(_t)

        if not extra_tools and bool(current_app.config.get("DEFAULT_WEB_SEARCH")):
            responses_tool_choice = payload.get("responses_tool_choice")
            if not (isinstance(responses_tool_choice, str) and responses_tool_choice == "none"):
                extra_tools = [{"type": "web_search"}]

        if extra_tools:
            import json as _json
            MAX_TOOLS_BYTES = 32768
            try:
                size = len(_json.dumps(extra_tools))
            except Exception:
                size = 0
            if size > MAX_TOOLS_BYTES:
                err = {"error": {"message": "responses_tools too large", "code": "RESPONSES_TOOLS_TOO_LARGE"}}
                if verbose:
                    _log_json("OUT POST /v1/chat/completions", err)
                return jsonify(err), 400
            had_responses_tools = True
            tools_responses = (tools_responses or []) + extra_tools

    responses_tool_choice = payload.get("responses_tool_choice")
    if isinstance(responses_tool_choice, str) and responses_tool_choice in ("auto", "none"):
        tool_choice = responses_tool_choice

    input_items = convert_chat_messages_to_responses_input(messages)
    if not input_items and isinstance(payload.get("prompt"), str) and payload.get("prompt").strip():
        input_items = [
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": payload.get("prompt")}]}
        ]

    # Inject specialized context message if content-type specified (Option C)
    try:
        specialized_msg = _get_specialized_context_message(content_type)
        if specialized_msg and input_items:
            input_items = [specialized_msg] + input_items
            if verbose:
                logger.info(f"Successfully injected specialized prompt: {content_type}")
    except Exception as e:
        logger.exception(f"Error injecting specialized prompt '{content_type}': {str(e)}")
        # Continue without specialized prompt - fallback to base instructions
        if verbose:
            logger.warning("Continuing without specialized prompt due to injection error")

    model_reasoning = extract_reasoning_from_model_name(requested_model)
    reasoning_overrides = payload.get("reasoning") if isinstance(payload.get("reasoning"), dict) else model_reasoning
    reasoning_param = build_reasoning_param(
        reasoning_effort,
        reasoning_summary,
        reasoning_overrides,
        allowed_efforts=allowed_efforts_for_model(model),
    )

    upstream, error_resp = start_upstream_request(
        model,
        input_items,
        instructions=_instructions_for_model(model, content_type),
        tools=tools_responses,
        tool_choice=tool_choice,
        parallel_tool_calls=parallel_tool_calls,
        reasoning_param=reasoning_param,
    )
    if error_resp is not None:
        if verbose:
            try:
                body = error_resp.get_data(as_text=True)
                if body:
                    try:
                        parsed = json.loads(body)
                    except Exception:
                        parsed = body
                    _log_json("OUT POST /v1/chat/completions", parsed)
            except Exception:
                pass
        return error_resp

    try:
        record_rate_limits_from_response(upstream)

        created = int(time.time())
        if upstream.status_code >= 400:
            try:
                raw = upstream.content
                err_body = json.loads(raw.decode("utf-8", errors="ignore")) if raw else {"raw": upstream.text}
            except Exception:
                err_body = {"raw": upstream.text}
            if had_responses_tools:
                if verbose:
                    print("[Passthrough] Upstream rejected tools; retrying without extra tools (args redacted)")
                base_tools_only = convert_tools_chat_to_responses(payload.get("tools"))
                safe_choice = payload.get("tool_choice", "auto")
                upstream2, err2 = start_upstream_request(
                    model,
                    input_items,
                    instructions=BASE_INSTRUCTIONS,
                    tools=base_tools_only,
                    tool_choice=safe_choice,
                    parallel_tool_calls=parallel_tool_calls,
                    reasoning_param=reasoning_param,
                )
                record_rate_limits_from_response(upstream2)
                if err2 is None and upstream2 is not None and upstream2.status_code < 400:
                    upstream.close()
                    upstream = upstream2
                else:
                    err = {
                        "error": {
                            "message": (err_body.get("error", {}) or {}).get("message", "Upstream error"),
                            "code": "RESPONSES_TOOLS_REJECTED",
                        }
                    }
                    if verbose:
                        _log_json("OUT POST /v1/chat/completions", err)
                    upstream.close()
                    if upstream2 is not None:
                        upstream2.close()
                    return jsonify(err), (upstream2.status_code if upstream2 is not None else upstream.status_code)
            else:
                if verbose:
                    print("Upstream error status=", upstream.status_code)
                err = {"error": {"message": (err_body.get("error", {}) or {}).get("message", "Upstream error")}}
                if verbose:
                    _log_json("OUT POST /v1/chat/completions", err)
                upstream.close()
                return jsonify(err), upstream.status_code
    except Exception as e:
        if upstream is not None:
            upstream.close()
        raise

    if is_stream:
        if verbose:
            print("OUT POST /v1/chat/completions (streaming response)")
        stream_iter = sse_translate_chat(
            upstream,
            requested_model or model,
            created,
            verbose=verbose_obfuscation,
            vlog=print if verbose_obfuscation else None,
            reasoning_compat=reasoning_compat,
            include_usage=include_usage,
        )
        stream_iter = _wrap_stream_logging("STREAM OUT /v1/chat/completions", stream_iter, verbose)
        resp = Response(
            stream_iter,
            status=upstream.status_code,
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    full_text = ""
    reasoning_summary_text = ""
    reasoning_full_text = ""
    response_id = "chatcmpl"
    tool_calls: List[Dict[str, Any]] = []
    error_message: str | None = None
    usage_obj: Dict[str, int] | None = None

    def _extract_usage(evt: Dict[str, Any]) -> Dict[str, int] | None:
        try:
            usage = (evt.get("response") or {}).get("usage")
            if not isinstance(usage, dict):
                return None
            pt = int(usage.get("input_tokens") or 0)
            ct = int(usage.get("output_tokens") or 0)
            tt = int(usage.get("total_tokens") or (pt + ct))
            return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt}
        except Exception:
            return None
    try:
        for raw in upstream.iter_lines(decode_unicode=False):
            if not raw:
                continue
            line = raw.decode("utf-8", errors="ignore") if isinstance(raw, (bytes, bytearray)) else raw
            if not line.startswith("data: "):
                continue
            data = line[len("data: "):].strip()
            if not data:
                continue
            if data == "[DONE]":
                break
            try:
                evt = json.loads(data)
            except Exception:
                continue
            if not isinstance(evt, dict):
                continue
            kind = evt.get("type")
            mu = _extract_usage(evt)
            if mu:
                usage_obj = mu
            if isinstance(evt.get("response"), dict) and isinstance(evt["response"].get("id"), str):
                response_id = evt["response"].get("id") or response_id
            if kind == "response.output_text.delta":
                full_text += evt.get("delta") or ""
            elif kind == "response.reasoning_summary_text.delta":
                reasoning_summary_text += evt.get("delta") or ""
            elif kind == "response.reasoning_text.delta":
                reasoning_full_text += evt.get("delta") or ""
            elif kind == "response.output_item.done":
                item = evt.get("item") or {}
                if isinstance(item, dict) and item.get("type") == "function_call":
                    call_id = item.get("call_id") or item.get("id") or ""
                    name = item.get("name") or ""
                    args = item.get("arguments") or ""
                    if isinstance(call_id, str) and isinstance(name, str) and isinstance(args, str):
                        tool_calls.append(
                            {
                                "id": call_id,
                                "type": "function",
                                "function": {"name": name, "arguments": args},
                            }
                        )
            elif kind == "response.failed":
                error_message = evt.get("response", {}).get("error", {}).get("message", "response.failed")
            elif kind == "response.completed":
                break
    finally:
        upstream.close()

    if error_message:
        resp = make_response(jsonify({"error": {"message": error_message}}), 502)
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    message: Dict[str, Any] = {"role": "assistant", "content": full_text if full_text else None}
    if tool_calls:
        message["tool_calls"] = tool_calls
    message = apply_reasoning_to_message(message, reasoning_summary_text, reasoning_full_text, reasoning_compat)
    completion = {
        "id": response_id or "chatcmpl",
        "object": "chat.completion",
        "created": created,
        "model": requested_model or model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "stop",
            }
        ],
        **({"usage": usage_obj} if usage_obj else {}),
    }
    if verbose:
        _log_json("OUT POST /v1/chat/completions", completion)
    # Validate upstream status code is a valid integer, default to 200
    status_code = upstream.status_code if isinstance(upstream.status_code, int) and 100 <= upstream.status_code < 600 else 200
    resp = make_response(jsonify(completion), status_code)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp


@openai_bp.route("/v1/completions", methods=["POST"])
def completions() -> Response:
    # Check rate limit
    if not _rate_limiter.is_allowed():
        retry_after = _rate_limiter.get_retry_after()
        err = {"error": {"message": "Rate limit exceeded"}}
        resp = jsonify(err)
        resp.status_code = 429
        resp.headers["Retry-After"] = str(retry_after)
        return resp

    verbose = bool(current_app.config.get("VERBOSE"))
    verbose_obfuscation = bool(current_app.config.get("VERBOSE_OBFUSCATION"))
    debug_model = current_app.config.get("DEBUG_MODEL")
    reasoning_effort = current_app.config.get("REASONING_EFFORT", "medium")
    reasoning_summary = current_app.config.get("REASONING_SUMMARY", "auto")
    content_type = request.headers.get("X-Prompt-Type", "").strip().lower() or None

    raw = request.get_data(cache=True, as_text=True) or ""
    if verbose:
        try:
            print("IN POST /v1/completions\n" + raw)
        except Exception:
            pass
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        err = {"error": {"message": "Invalid JSON body"}}
        if verbose:
            _log_json("OUT POST /v1/completions", err)
        return jsonify(err), 400

    requested_model = payload.get("model")
    model = normalize_model_name(requested_model, debug_model)

    # Validate model ID
    expose_variants = bool(current_app.config.get("EXPOSE_REASONING_MODELS"))
    if not _validate_model_id(requested_model, expose_variants):
        err = {"error": {"message": f"Model '{requested_model}' not found"}}
        if verbose:
            _log_json("OUT POST /v1/completions", err)
        return jsonify(err), 404

    prompt = payload.get("prompt")
    if isinstance(prompt, list):
        prompt = "".join([p if isinstance(p, str) else "" for p in prompt])
    if not isinstance(prompt, str):
        prompt = payload.get("suffix") or ""
    stream_req = bool(payload.get("stream", False))
    stream_options = payload.get("stream_options") if isinstance(payload.get("stream_options"), dict) else {}
    include_usage = bool(stream_options.get("include_usage", False))

    messages = [{"role": "user", "content": prompt or ""}]
    input_items = convert_chat_messages_to_responses_input(messages)

    # Inject specialized context message if content-type specified (Option C)
    try:
        specialized_msg = _get_specialized_context_message(content_type)
        if specialized_msg and input_items:
            input_items = [specialized_msg] + input_items
            if verbose:
                logger.info(f"Successfully injected specialized prompt: {content_type}")
    except Exception as e:
        logger.exception(f"Error injecting specialized prompt '{content_type}': {str(e)}")
        # Continue without specialized prompt - fallback to base instructions
        if verbose:
            logger.warning("Continuing without specialized prompt due to injection error")

    model_reasoning = extract_reasoning_from_model_name(requested_model)
    reasoning_overrides = payload.get("reasoning") if isinstance(payload.get("reasoning"), dict) else model_reasoning
    reasoning_param = build_reasoning_param(
        reasoning_effort,
        reasoning_summary,
        reasoning_overrides,
        allowed_efforts=allowed_efforts_for_model(model),
    )
    upstream, error_resp = start_upstream_request(
        model,
        input_items,
        instructions=_instructions_for_model(model, content_type),
        reasoning_param=reasoning_param,
    )
    if error_resp is not None:
        if verbose:
            try:
                body = error_resp.get_data(as_text=True)
                if body:
                    try:
                        parsed = json.loads(body)
                    except Exception:
                        parsed = body
                    _log_json("OUT POST /v1/completions", parsed)
            except Exception:
                pass
        return error_resp

    record_rate_limits_from_response(upstream)

    created = int(time.time())
    if upstream.status_code >= 400:
        try:
            err_body = json.loads(upstream.content.decode("utf-8", errors="ignore")) if upstream.content else {"raw": upstream.text}
        except Exception:
            err_body = {"raw": upstream.text}
        err = {"error": {"message": (err_body.get("error", {}) or {}).get("message", "Upstream error")}}
        if verbose:
            _log_json("OUT POST /v1/completions", err)
        return jsonify(err), upstream.status_code

    if stream_req:
        if verbose:
            print("OUT POST /v1/completions (streaming response)")
        stream_iter = sse_translate_text(
            upstream,
            requested_model or model,
            created,
            verbose=verbose_obfuscation,
            vlog=(print if verbose_obfuscation else None),
            include_usage=include_usage,
        )
        stream_iter = _wrap_stream_logging("STREAM OUT /v1/completions", stream_iter, verbose)
        resp = Response(
            stream_iter,
            status=upstream.status_code,
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    full_text = ""
    response_id = "cmpl"
    usage_obj: Dict[str, int] | None = None
    def _extract_usage(evt: Dict[str, Any]) -> Dict[str, int] | None:
        try:
            usage = (evt.get("response") or {}).get("usage")
            if not isinstance(usage, dict):
                return None
            pt = int(usage.get("input_tokens") or 0)
            ct = int(usage.get("output_tokens") or 0)
            tt = int(usage.get("total_tokens") or (pt + ct))
            return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt}
        except Exception:
            return None
    try:
        for raw_line in upstream.iter_lines(decode_unicode=False):
            if not raw_line:
                continue
            line = raw_line.decode("utf-8", errors="ignore") if isinstance(raw_line, (bytes, bytearray)) else raw_line
            if not line.startswith("data: "):
                continue
            data = line[len("data: "):].strip()
            if not data or data == "[DONE]":
                if data == "[DONE]":
                    break
                continue
            try:
                evt = json.loads(data)
            except Exception:
                continue
            if isinstance(evt.get("response"), dict) and isinstance(evt["response"].get("id"), str):
                response_id = evt["response"].get("id") or response_id
            mu = _extract_usage(evt)
            if mu:
                usage_obj = mu
            kind = evt.get("type")
            if kind == "response.output_text.delta":
                full_text += evt.get("delta") or ""
            elif kind == "response.completed":
                break
    finally:
        upstream.close()

    completion = {
        "id": response_id or "cmpl",
        "object": "text_completion",
        "created": created,
        "model": requested_model or model,
        "choices": [
            {"index": 0, "text": full_text, "finish_reason": "stop", "logprobs": None}
        ],
        **({"usage": usage_obj} if usage_obj else {}),
    }
    if verbose:
        _log_json("OUT POST /v1/completions", completion)
    resp = make_response(jsonify(completion), upstream.status_code)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp


@openai_bp.route("/health", methods=["GET"])
def health_check() -> Response:
    """Health check endpoint for production monitoring."""
    try:
        # Check basic configuration
        prompts = current_app.config.get("CONTENT_TYPE_PROMPTS")
        base_instructions = current_app.config.get("BASE_INSTRUCTIONS")

        health_status = {
            "status": "healthy",
            "timestamp": int(time.time()),
            "checks": {
                "config": "ok" if (base_instructions and prompts) else "degraded",
                "specialized_prompts": "ok" if isinstance(prompts, dict) and len(prompts) > 0 else "degraded",
            }
        }

        if health_status["checks"]["config"] == "degraded":
            logger.warning("Health check: config is degraded")
            health_status["status"] = "degraded"

        status_code = 200 if health_status["status"] == "healthy" else 503
        resp = make_response(jsonify(health_status), status_code)
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    except Exception as e:
        logger.exception(f"Health check failed: {str(e)}")
        error_response = {
            "status": "unhealthy",
            "timestamp": int(time.time()),
            "error": str(e)
        }
        resp = make_response(jsonify(error_response), 503)
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp


@openai_bp.route("/v1/models", methods=["GET"])
def list_models() -> Response:
    expose_variants = bool(current_app.config.get("EXPOSE_REASONING_MODELS"))
    model_ids: List[str] = []
    for base, efforts in _MODEL_GROUPS:
        model_ids.append(base)
        if expose_variants:
            model_ids.extend([f"{base}-{effort}" for effort in efforts])
    data = [{"id": mid, "object": "model", "owned_by": "owner"} for mid in model_ids]
    models = {"object": "list", "data": data}
    resp = make_response(jsonify(models), 200)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp
