import base64
import json
import logging
from typing import Any, Dict, Optional

from .services.chat_service import ChatService, LearningPathNotFound, SessionNotFound
from .utils import http
from .utils.auth import extract_user_id

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    global _service
    if _service is None:
        _service = ChatService()
    return _service


def _normalize_path(event: Dict[str, Any]) -> str:
    raw_path = event.get("rawPath") or event.get("path") or ""
    stage = event.get("requestContext", {}).get("stage")
    if stage and raw_path.startswith(f"/{stage}"):
        return raw_path[len(stage) + 1 :]
    return raw_path.lstrip("/")


def _parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    body = event.get("body")
    if body is None:
        return {}
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")  # type: ignore[name-defined]
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError("Body must be valid JSON") from exc
    if isinstance(body, dict):
        return body
    raise ValueError("Unsupported body format")


def lambda_handler(event: Dict[str, Any], _context: Any) -> Dict[str, Any]:
    method = (event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod") or "").upper()

    if method == "OPTIONS":
        return http.no_content()

    path = _normalize_path(event)
    logger.info("Incoming request: %s %s", method, path)

    user_id = extract_user_id(event)
    if not user_id:
        return http.unauthorized("Missing authenticated user")

    service = get_chat_service()

    try:
        if method == "POST" and path == "chat/message":
            body = _parse_body(event)
            message = (body.get("message") or "").strip()
            learning_path_id = body.get("learning_path_id") or body.get("path_id")
            session_id = body.get("session_id")

            if not message:
                return http.bad_request("El mensaje no puede estar vacío", "EMPTY_MESSAGE")
            if not learning_path_id:
                return http.bad_request(
                    "Debes seleccionar una ruta de aprendizaje antes de usar el chat.",
                    "NO_LEARNING_PATH",
                )

            payload = service.send_message(
                user_id=user_id,
                learning_path_id=learning_path_id,
                message=message,
                session_id=session_id,
            )
            return http.response(200, payload)

        if method == "GET" and path.startswith("chat/history/"):
            session_id = path.split("/", maxsplit=2)[-1]
            if not session_id:
                return http.bad_request("session_id es requerido", "MISSING_SESSION_ID")
            history = service.get_history(user_id=user_id, session_id=session_id)
            return http.response(200, {"session_id": session_id, "messages": history})

        if method == "GET" and path == "chat/sessions":
            query = event.get("queryStringParameters") or {}
            learning_path_id = query.get("learning_path_id")
            sessions = service.list_sessions(
                user_id=user_id, learning_path_id=learning_path_id
            )
            return http.response(200, {"sessions": sessions})

        if method == "DELETE" and path.startswith("chat/session/"):
            session_id = path.split("/", maxsplit=2)[-1]
            if not session_id:
                return http.bad_request("session_id es requerido", "MISSING_SESSION_ID")
            service.delete_session(user_id=user_id, session_id=session_id)
            return http.no_content()

        return http.not_found("Ruta no disponible", "ROUTE_NOT_FOUND")

    except LearningPathNotFound:
        return http.bad_request(
            "No encontramos la ruta de aprendizaje seleccionada.",
            "UNKNOWN_LEARNING_PATH",
        )
    except SessionNotFound:
        return http.not_found("La sesión indicada no existe.", "SESSION_NOT_FOUND")
    except PermissionError as exc:
        logger.warning("Permission error: %s", exc)
        return http.unauthorized(str(exc))
    except ValueError as exc:
        logger.warning("Bad request: %s", exc)
        return http.bad_request(str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error processing chat request")
        return http.internal_error()
