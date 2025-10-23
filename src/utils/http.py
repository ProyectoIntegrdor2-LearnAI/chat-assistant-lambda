import json
import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse

RAW_CORS_ORIGIN = os.getenv("CORS_ALLOW_ORIGIN", "https://www.learn-ia.app")


def _normalize_origin(origin: Optional[str]) -> Optional[str]:
    if not origin:
        return None
    origin = origin.strip()
    if origin == "*":
        return "*"

    parsed = urlparse(origin if "://" in origin else f"https://{origin.lstrip('/')}")
    host = parsed.hostname or ""
    scheme = parsed.scheme or "https"
    port = f":{parsed.port}" if parsed.port else ""
    normalized = f"{scheme.lower()}://{host.lower()}{port}"
    return normalized.rstrip("/") or None


def _build_cors_headers(request_origin: Optional[str] = None) -> Dict[str, str]:
    allowed_origin = _normalize_origin(RAW_CORS_ORIGIN) or "*"
    incoming_origin = _normalize_origin(request_origin)

    allow_origin: str
    if allowed_origin == "*":
        allow_origin = "*" if incoming_origin is None else incoming_origin
    elif incoming_origin and incoming_origin == allowed_origin:
        allow_origin = incoming_origin
    else:
        allow_origin = allowed_origin

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


def response(
    status_code: int,
    body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    request_origin: Optional[str] = None,
) -> Dict[str, Any]:
    final_headers = _build_cors_headers(request_origin)
    if headers:
        final_headers.update(headers)
    payload = "" if body is None else json.dumps(body, ensure_ascii=False)
    return {
        "statusCode": status_code,
        "headers": final_headers,
        "body": payload,
    }


def no_content(request_origin: Optional[str] = None) -> Dict[str, Any]:
    return response(204, None, request_origin=request_origin)


def bad_request(
    message: str, code: str = "BAD_REQUEST", request_origin: Optional[str] = None
) -> Dict[str, Any]:
    return response(
        400,
        {
            "error": code,
            "message": message,
        },
        request_origin=request_origin,
    )


def unauthorized(
    message: str = "Unauthorized", request_origin: Optional[str] = None
) -> Dict[str, Any]:
    return response(
        401,
        {
            "error": "UNAUTHORIZED",
            "message": message,
        },
        request_origin=request_origin,
    )


def not_found(
    message: str = "Not found", code: str = "NOT_FOUND", request_origin: Optional[str] = None
) -> Dict[str, Any]:
    return response(
        404,
        {
            "error": code,
            "message": message,
        },
        request_origin=request_origin,
    )


def internal_error(
    message: str = "Internal server error", request_origin: Optional[str] = None
) -> Dict[str, Any]:
    return response(
        500,
        {
            "error": "INTERNAL_ERROR",
            "message": message,
        },
        request_origin=request_origin,
    )
