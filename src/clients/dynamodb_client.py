import os
import time
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from boto3.dynamodb.conditions import Key


class ChatHistoryRepository:
    def __init__(self) -> None:
        table_name = os.getenv("CHAT_SESSIONS_TABLE")
        if not table_name:
            raise ValueError("CHAT_SESSIONS_TABLE environment variable is required")

        session_ttl_days = int(os.getenv("SESSION_TTL_DAYS", "30"))
        self._history_limit = int(os.getenv("MAX_HISTORY_MESSAGES", "10"))
        self._ttl_seconds = session_ttl_days * 24 * 60 * 60

        self._dynamodb = boto3.resource("dynamodb")
        self._table = self._dynamodb.Table(table_name)
        self._gsi_name = os.getenv("CHAT_SESSIONS_GSI", "UserPathIndex")

    @property
    def history_limit(self) -> int:
        return self._history_limit

    @staticmethod
    def _now_epoch() -> int:
        return int(time.time())

    def _compute_ttl(self) -> int:
        return self._now_epoch() + self._ttl_seconds

    def _make_timestamp(self) -> Decimal:
        return Decimal(str(time.time()))

    def create_session_id(self) -> str:
        return str(uuid.uuid4())

    def append_message(
        self,
        *,
        session_id: str,
        user_id: str,
        learning_path_id: str,
        role: str,
        message: str,
    ) -> None:
        item = {
            "session_id": session_id,
            "timestamp": self._make_timestamp(),
            "user_id": user_id,
            "learning_path_id": learning_path_id,
            "role": role,
            "message": message,
            "ttl": self._compute_ttl(),
        }
        try:
            self._table.put_item(Item=item)
        except (ClientError, BotoCoreError) as exc:
            raise RuntimeError(f"Failed to append chat message: {exc}") from exc

    def get_session_messages(
        self, session_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        limit = limit or self._history_limit
        try:
            response = self._table.query(
                KeyConditionExpression=Key("session_id").eq(session_id),
                ScanIndexForward=True,
                Limit=limit,
            )
        except (ClientError, BotoCoreError) as exc:
            raise RuntimeError(f"Failed to fetch session history: {exc}") from exc

        items = response.get("Items", [])
        # DynamoDB may return Decimal objects
        for item in items:
            ts = item.get("timestamp")
            if isinstance(ts, Decimal):
                item["timestamp"] = float(ts)
        return items

    def get_session_owner(self, session_id: str) -> Optional[str]:
        try:
            response = self._table.query(
                KeyConditionExpression=Key("session_id").eq(session_id),
                ProjectionExpression="user_id",
                Limit=1,
            )
        except (ClientError, BotoCoreError) as exc:
            raise RuntimeError(f"Failed to resolve session owner: {exc}") from exc

        items = response.get("Items", [])
        if not items:
            return None
        return items[0].get("user_id")

    def list_sessions(self, user_id: str, learning_path_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lista las sesiones activas para un usuario. Si se provee learning_path_id
        se filtra por ruta; de lo contrario se devuelven todas.
        """
        try:
            key_condition = Key("user_id").eq(user_id)
            if learning_path_id:
                key_condition &= Key("learning_path_id").eq(learning_path_id)

            response = self._table.query(
                IndexName=self._gsi_name,
                KeyConditionExpression=key_condition,
                ProjectionExpression="session_id, learning_path_id, #ts, role, message",
                ExpressionAttributeNames={"#ts": "timestamp"},
            )
        except (ClientError, BotoCoreError) as exc:
            raise RuntimeError(f"Failed to query sessions: {exc}") from exc

        items = response.get("Items", [])
        normalized: Dict[str, Dict[str, Any]] = {}
        for item in items:
            session_id = item["session_id"]
            ts = item.get("timestamp")
            if isinstance(ts, Decimal):
                ts = float(ts)

            record = normalized.setdefault(
                session_id,
                {
                    "session_id": session_id,
                    "learning_path_id": item.get("learning_path_id"),
                    "last_message_role": item.get("role"),
                    "last_message": item.get("message"),
                    "last_timestamp": ts or 0.0,
                },
            )
            if ts and ts > record.get("last_timestamp", 0.0):
                record["last_timestamp"] = ts
                record["last_message_role"] = item.get("role")
                record["last_message"] = item.get("message")
        return list(normalized.values())

    def delete_session(self, session_id: str) -> None:
        """
        Elimina todos los items asociados a una sesión usando un batch write.
        """
        messages = self.get_session_messages(session_id, limit=1000)
        if not messages:
            return
        try:
            with self._table.batch_writer() as batch:
                for item in messages:
                    batch.delete_item(
                        Key={
                            "session_id": session_id,
                            "timestamp": Decimal(str(item["timestamp"])),
                        }
                    )
        except (ClientError, BotoCoreError) as exc:
            raise RuntimeError(f"Failed to delete session {session_id}: {exc}") from exc
