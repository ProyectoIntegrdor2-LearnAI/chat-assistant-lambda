from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from clients.bedrock_client import BedrockClient
from clients.dynamodb_client import ChatHistoryRepository
from services.context_builder import (
    LearningPathContextBuilder,
    LearningPathNotFound,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SessionNotFound(Exception):
    """Raised when a session_id does not exist for the user."""


class ChatService:
    def __init__(
        self,
        bedrock_client: Optional[BedrockClient] = None,
        history_repository: Optional[ChatHistoryRepository] = None,
        context_builder: Optional[LearningPathContextBuilder] = None,
    ) -> None:
        self._bedrock = bedrock_client or BedrockClient()
        self._history_repo = history_repository or ChatHistoryRepository()
        self._context_builder = context_builder or LearningPathContextBuilder()

    def send_message(
        self,
        *,
        user_id: str,
        learning_path_id: str,
        message: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not message or not message.strip():
            raise ValueError("Message cannot be empty")

        if session_id:
            owner = self._history_repo.get_session_owner(session_id)
            if owner and owner != user_id:
                raise PermissionError("Session does not belong to the user")
            if owner is None:
                raise SessionNotFound("Session not found")

        if session_id is None:
            session_id = self._history_repo.create_session_id()

        try:
            context = self._context_builder.build_context(user_id, learning_path_id)
        except LearningPathNotFound as exc:
            logger.warning("Learning path not found for chat: %s", exc)
            raise

        system_prompt = self._context_builder.build_system_prompt(context)
        history_items = self._history_repo.get_session_messages(session_id)
        limit = getattr(self._history_repo, "history_limit", 10)

        conversation: List[Dict[str, str]] = []
        for turn in history_items[-limit:]:
            conversation.append(
                {
                    "role": turn.get("role", "user"),
                    "content": turn.get("message", ""),
                }
            )
        conversation.append({"role": "user", "content": message})

        ai_response: str
        try:
            logger.info(
                "Invoking Bedrock for session %s (user %s, lp %s)",
                session_id,
                user_id,
                learning_path_id,
            )
            ai_response = self._bedrock.invoke(system_prompt, conversation)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Bedrock invocation failed: %s", exc)
            ai_response = (
                "Por el momento no puedo consultar tu tutor inteligente. "
                "Sigue avanzando con tu ruta y vuelve a intentarlo en unos minutos."
            )

        # Persist messages
        self._history_repo.append_message(
            session_id=session_id,
            user_id=user_id,
            learning_path_id=learning_path_id,
            role="user",
            message=message,
        )
        self._history_repo.append_message(
            session_id=session_id,
            user_id=user_id,
            learning_path_id=learning_path_id,
            role="assistant",
            message=ai_response,
        )

        return {
            "session_id": session_id,
            "learning_path_id": learning_path_id,
            "response": ai_response,
            "context": {
                "overall_progress": context.get("overall_progress"),
                "current_course": context.get("current_course"),
                "next_course": context.get("next_course"),
            },
        }

    def get_history(self, *, user_id: str, session_id: str) -> List[Dict[str, Any]]:
        owner = self._history_repo.get_session_owner(session_id)
        if owner and owner != user_id:
            raise PermissionError("Session does not belong to the user")
        history = self._history_repo.get_session_messages(session_id, limit=100)
        return [
            {
                "role": item.get("role"),
                "message": item.get("message"),
                "timestamp": item.get("timestamp"),
            }
            for item in history
        ]

    def list_sessions(
        self, *, user_id: str, learning_path_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        sessions = self._history_repo.list_sessions(user_id, learning_path_id)
        return sessions

    def delete_session(self, *, user_id: str, session_id: str) -> None:
        owner = self._history_repo.get_session_owner(session_id)
        if owner and owner != user_id:
            raise PermissionError("Session does not belong to the user")
        self._history_repo.delete_session(session_id)
