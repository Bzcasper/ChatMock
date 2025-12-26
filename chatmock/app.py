from __future__ import annotations

import datetime

from flask import Flask, jsonify

from .config import BASE_INSTRUCTIONS, GPT5_CODEX_INSTRUCTIONS, CONTENT_TYPE_PROMPTS
from .http import build_cors_headers
from .routes_openai import openai_bp
from .routes_ollama import ollama_bp
from .utils import load_chatgpt_tokens, parse_jwt_claims, eprint


def create_app(
    verbose: bool = False,
    verbose_obfuscation: bool = False,
    reasoning_effort: str = "medium",
    reasoning_summary: str = "auto",
    reasoning_compat: str = "think-tags",
    debug_model: str | None = None,
    expose_reasoning_models: bool = False,
    default_web_search: bool = False,
) -> Flask:
    app = Flask(__name__)

    app.config.update(
        VERBOSE=bool(verbose),
        VERBOSE_OBFUSCATION=bool(verbose_obfuscation),
        REASONING_EFFORT=reasoning_effort,
        REASONING_SUMMARY=reasoning_summary,
        REASONING_COMPAT=reasoning_compat,
        DEBUG_MODEL=debug_model,
        BASE_INSTRUCTIONS=BASE_INSTRUCTIONS,
        GPT5_CODEX_INSTRUCTIONS=GPT5_CODEX_INSTRUCTIONS,
        CONTENT_TYPE_PROMPTS=CONTENT_TYPE_PROMPTS,
        EXPOSE_REASONING_MODELS=bool(expose_reasoning_models),
        DEFAULT_WEB_SEARCH=bool(default_web_search),
    )

    @app.get("/")
    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/health/tokens")
    def health_tokens():
        try:
            access_token, account_id, id_token = load_chatgpt_tokens(ensure_fresh=False)

            if not access_token:
                return jsonify({
                    "status": "unhealthy",
                    "reason": "No access token available",
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }), 503

            claims = parse_jwt_claims(access_token) or {}
            exp = claims.get("exp")

            if not isinstance(exp, (int, float)):
                return jsonify({
                    "status": "warning",
                    "reason": "Unable to parse token expiry",
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }), 200

            now = datetime.datetime.now(datetime.timezone.utc)
            expiry = datetime.datetime.fromtimestamp(float(exp), datetime.timezone.utc)
            time_until_expiry = (expiry - now).total_seconds()

            if time_until_expiry < 0:
                return jsonify({
                    "status": "unhealthy",
                    "reason": "Token has expired",
                    "expires_in_seconds": int(time_until_expiry),
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }), 503

            if time_until_expiry < 300:
                return jsonify({
                    "status": "warning",
                    "reason": "Token expiring soon",
                    "expires_in_seconds": int(time_until_expiry),
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }), 200

            return jsonify({
                "status": "healthy",
                "expires_in_seconds": int(time_until_expiry),
                "account_id": account_id,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }), 200

        except Exception as exc:
            eprint(f"Health check error: {exc}")
            return jsonify({
                "status": "unhealthy",
                "error": str(exc),
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }), 503

    @app.after_request
    def _cors(resp):
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    app.register_blueprint(openai_bp)
    app.register_blueprint(ollama_bp)

    return app
