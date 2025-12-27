from __future__ import annotations

import os
from flask import Response, jsonify, request

# Load allowed CORS origins from environment or use defaults
ALLOWED_ORIGINS = os.getenv("ALLOWED_CORS_ORIGINS", "").split(",") if os.getenv("ALLOWED_CORS_ORIGINS") else ["*"]
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()]


def _validate_origin(origin: str | None) -> str:
    """Validate requested origin against whitelist. Returns safe origin or '*'."""
    if not origin:
        return ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else "*"

    if "*" in ALLOWED_ORIGINS:
        return origin

    if origin in ALLOWED_ORIGINS:
        return origin

    # Origin not in whitelist - return first allowed origin
    return ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else "*"


def build_cors_headers() -> dict[str, str]:
    origin = request.headers.get("Origin")
    validated_origin = _validate_origin(origin)
    req_headers = request.headers.get("Access-Control-Request-Headers")
    allow_headers = req_headers if req_headers else "Authorization, Content-Type, Accept"

    return {
        "Access-Control-Allow-Origin": validated_origin,
        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        "Access-Control-Allow-Headers": allow_headers,
        "Access-Control-Max-Age": "86400",
    }


def json_error(message: str, status: int = 400) -> Response:
    resp = jsonify({"error": {"message": message}})
    response: Response = Response(response=resp.response, status=status, mimetype="application/json")
    for k, v in build_cors_headers().items():
        response.headers.setdefault(k, v)
    return response

