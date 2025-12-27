from __future__ import annotations

import os
import sys
from pathlib import Path


CLIENT_ID_DEFAULT = os.getenv("CHATGPT_LOCAL_CLIENT_ID") or "app_EMoamEEZ73f0CkXaXp7hrann"
OAUTH_ISSUER_DEFAULT = os.getenv("CHATGPT_LOCAL_ISSUER") or "https://auth.openai.com"
OAUTH_TOKEN_URL = f"{OAUTH_ISSUER_DEFAULT}/oauth/token"

CHATGPT_RESPONSES_URL = os.getenv("CHATGPT_RESPONSES_URL") or "https://chatgpt.com/backend-api/codex/responses"

# Default fallback prompt if prompt.md is not found
DEFAULT_BASE_INSTRUCTIONS = (
    "You are a helpful AI assistant. Respond clearly and accurately to user queries. "
    "Maintain context throughout the conversation and provide thoughtful, well-reasoned responses."
)


def _read_prompt_text(filename: str) -> str | None:
    candidates = [
        Path(__file__).parent.parent / filename,
        Path(__file__).parent / filename,
        Path(getattr(sys, "_MEIPASS", "")) / filename if getattr(sys, "_MEIPASS", None) else None,
        Path.cwd() / filename,
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            if candidate.exists():
                content = candidate.read_text(encoding="utf-8")
                if isinstance(content, str) and content.strip():
                    return content
        except Exception:
            continue
    return None


def read_base_instructions() -> str:
    content = _read_prompt_text("prompt.md")
    if content is None:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            "prompt.md not found; using default base instructions. "
            "Consider placing prompt.md in project root or current working directory."
        )
        return DEFAULT_BASE_INSTRUCTIONS
    return content


def read_gpt5_codex_instructions(fallback: str) -> str:
    content = _read_prompt_text("prompt_gpt5_codex.md")
    return content if isinstance(content, str) and content.strip() else fallback


BASE_INSTRUCTIONS = read_base_instructions()
GPT5_CODEX_INSTRUCTIONS = read_gpt5_codex_instructions(BASE_INSTRUCTIONS)


def load_content_type_prompts() -> dict[str, str]:
    """
    Load specialized prompts for different content types.
    Used for video generation, storytelling, screenplay, etc.
    """
    content_types = {
        'story': 'prompt_story.md',
        'script': 'prompt_script.md',
        'screenplay': 'prompt_script.md',
        'dialogue': 'prompt_dialogue.md',
        'storyboard': 'prompt_storyboard.md',
        'image': 'prompt_image.md',
    }

    prompts = {}
    for content_type, filename in content_types.items():
        content = _read_prompt_text(filename)
        if content is not None and isinstance(content, str) and content.strip():
            prompts[content_type] = content

    return prompts


CONTENT_TYPE_PROMPTS = load_content_type_prompts()
