import json
from typing import Any, Dict, Optional


def extract_user_id(event: Dict[str, Any]) -> Optional[str]:
    # Cognito JWT claims (HTTP API payload)
    request_context = event.get("requestContext") or {}
    authorizer = request_context.get("authorizer") or {}

    # HTTP API
    jwt_claims = authorizer.get("jwt", {}).get("claims") or {}
    if "sub" in jwt_claims:
        return jwt_claims["sub"]

    # REST API custom authorizer
    claims = authorizer.get("claims") or {}
    if "sub" in claims:
        return claims["sub"]

    # Legacy support via headers
    headers = event.get("headers") or {}
    for key in ("x-user-id", "user-id", "X-User-Id", "User-Id"):
        if headers.get(key):
            return headers[key]

    body = event.get("body")
    if body:
        try:
            if isinstance(body, str):
                body = json.loads(body)
            if isinstance(body, dict):
                user_id = body.get("user_id") or body.get("userId")
                if user_id:
                    return user_id
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
    return None
