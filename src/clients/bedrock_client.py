import json
import logging
import os
from typing import Iterable, List, Dict, Any

import boto3
from botocore.config import Config
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


class BedrockClient:
    def __init__(self) -> None:
        region = os.getenv("BEDROCK_REGION", "us-west-2")
        model_id = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0")
        temperature = float(os.getenv("BEDROCK_TEMPERATURE", "0.7"))
        max_tokens = int(os.getenv("BEDROCK_MAX_TOKENS", "2048"))

        self._model_id = model_id
        self._temperature = temperature
        self._max_tokens = max_tokens

        logger.info(
            "Initializing Bedrock client",
            extra={
                "bedrock_region": region,
                "bedrock_model_id": model_id,
            },
        )

        config = Config(
            region_name=region,
            retries={"max_attempts": 3, "mode": "standard"},
            read_timeout=30,
            connect_timeout=5,
            max_pool_connections=15,
        )

        logger.info(
            "Initializing Bedrock runtime client",
            extra={
                "bedrock_region": region,
                "bedrock_model_id": model_id,
            },
        )

        self._client = boto3.client("bedrock-runtime", region_name=region, config=config)

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(4),
        retry=(
            retry_if_exception_type(ClientError)
            | retry_if_exception_type(BotoCoreError)
        ),
        reraise=True,
    )
    def invoke(
        self,
        system_prompt: str,
        conversation: Iterable[Dict[str, str]],
    ) -> str:
        """
        Ejecuta una conversación con Bedrock Nova usando un system prompt y el historial.
        conversation: iterable de dicts con keys `role` ('user'|'assistant') y `content`.
        """
        sanitized_history: List[Dict[str, str]] = []
        for turn in conversation:
            role = (turn.get("role") or "user").lower()
            if role not in {"user", "assistant"}:
                continue
            content = str(turn.get("content") or "")
            if not content.strip():
                continue
            sanitized_history.append({"role": role, "content": content})

        if not sanitized_history:
            sanitized_history.append({"role": "user", "content": ""})

        first_turn = sanitized_history[0]
        first_message_text = f"{system_prompt.strip()}\n\n{first_turn['content']}".strip()

        messages: List[Dict[str, Any]] = [
            {
                "role": "user",
                "content": [{"text": first_message_text}],
            }
        ]

        for turn in sanitized_history[1:]:
            messages.append(
                {
                    "role": turn["role"],
                    "content": [{"text": turn["content"]}],
                }
            )

        payload = {
            "messages": messages,
            "inferenceConfig": {
                "temperature": self._temperature,
                "maxTokens": self._max_tokens,
                "topP": 0.9,
            },
        }

        response = self._client.invoke_model(
            modelId=self._model_id,
            accept="application/json",
            contentType="application/json",
            body=json.dumps(payload),
        )

        raw_content = json.loads(response["body"].read())
        # Nova responses may include `output` or `results`
        if "output" in raw_content:
            return _extract_text(raw_content["output"])
        if "results" in raw_content:
            return _extract_text(raw_content["results"])
        return _extract_text(raw_content)


def _extract_text(content: Any) -> str:
    if isinstance(content, dict):
        # Check nested structures
        message = content.get("message")
        if isinstance(message, dict):
            text_blocks = message.get("content", [])
            for block in text_blocks:
                if isinstance(block, dict) and "text" in block:
                    return block["text"]
        if "text" in content:
            return str(content["text"])

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        if parts:
            return "\n".join(parts)

    return str(content)
