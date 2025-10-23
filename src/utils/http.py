import json
import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse

RAW_CORS_ORIGIN = os.getenv("CORS_ALLOW_ORIGIN", "https://www.learn-ia.app")


def _normalize_origin(origin: Optional[str]) -> str:
    if not origin:
        return "*"
    origin = origin.strip()
    if origin == "*":
        return "*"

    parsed = urlparse(origin if "://" in origin else f"https://{origin.lstrip('/')}")
    host = parsed.hostname or ""
    scheme = parsed.scheme or "https"
    port = f":{parsed.port}" if parsed.port else ""
    normalized = f"{scheme.lower()}://{host.lower()}{port}"
    return normalized.rstrip("/")


def _build_cors_headers() -> Dict[str, str]:
    allow_origin = _normalize_origin(RAW_CORS_ORIGIN)
    headers = {
        "Access-Control-Allow-Origin": allow_origin,
        "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-User-Id",
        "Access-Control-Allow-Credentials": "false",
    }
    if allow_origin != "*":
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Vary"] = "Origin"
    return headers


CORS_HEADERS = _build_cors_headers()


def response(
    status_code: int,
    body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    final_headers = {**CORS_HEADERS}
    if headers:
        final_headers.update(headers)
    payload = "" if body is None else json.dumps(body, ensure_ascii=False)
    return {
        "statusCode": status_code,
        "headers": final_headers,
        "body": payload,
    }


def no_content() -> Dict[str, Any]:
    return response(204, None)


def bad_request(message: str, code: str = "BAD_REQUEST") -> Dict[str, Any]:
    return response(
        400,
        {
            "error": code,
            "message": message,
        },
    )


def unauthorized(message: str = "Unauthorized") -> Dict[str, Any]:
    return response(
        401,
        {
            "error": "UNAUTHORIZED",
            "message": message,
        },
    )


def not_found(message: str = "Not found", code: str = "NOT_FOUND") -> Dict[str, Any]:
    return response(
        404,
        {
            "error": code,
            "message": message,
        },
    )


def internal_error(message: str = "Internal server error") -> Dict[str, Any]:
    return response(
        500,
        {
            "error": "INTERNAL_ERROR",
            "message": message,
        },
    )
