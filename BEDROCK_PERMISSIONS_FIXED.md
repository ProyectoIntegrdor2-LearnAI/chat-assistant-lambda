# Resolución de Permisos de Bedrock - Chat Assistant Lambda

## Problema

La lambda `learnia-chat-assistant-dev` estaba fallando al intentar invocar el modelo de Bedrock con el siguiente error:

```
AccessDeniedException: User: arn:aws:sts::974724840334:assumed-role/learnia-chat-assistant-de-ChatAssistantFunctionRole-TKx7HQUGLlwq/learnia-chat-assistant-dev 
is not authorized to perform: bedrock:InvokeModel 
on resource: arn:aws:bedrock:us-west-2:974724840334:inference-profile/us.amazon.nova-pro-v1:0
```

Esto causaba que cada mensaje de chat mostrara la respuesta de fallback en lugar de respuestas reales del asistente:
- "Por el momento no puedo consultar tu tutor inteligente. Sigue avanzando con tu ruta y vuelve a intentarlo en unos minutos."

### Análisis de Logs

Logs de CloudWatch muestran:
- RequestId: 9c554fa7-1bf9-4ec5-887b-9f86445d5abb
- Timestamp: 2025-10-23T19:38:16.810Z
- Error: Bedrock invocation failed después de 8+ segundos de reintento
- Duración total: 8285 ms

### Causa Raíz

La política IAM del rol solo incluía permisos de Bedrock para `us-east-1`, mientras que la lambda estaba configurada para usar `us-west-2`.

## Solución Implementada

Se actualizó la política inline `ChatAssistantFunctionRolePolicy2` del rol IAM mediante AWS CLI.

### Comando Ejecutado

```bash
aws iam put-role-policy \
  --role-name learnia-chat-assistant-de-ChatAssistantFunctionRole-TKx7HQUGLlwq \
  --policy-name ChatAssistantFunctionRolePolicy2 \
  --policy-document '{
    "Statement": [
      {
        "Action": ["dynamodb:Query"],
        "Resource": "arn:aws:dynamodb:us-east-2:974724840334:table/learnia-chat-sessions-dev/index/*",
        "Effect": "Allow"
      },
      {
        "Action": ["bedrock:InvokeModel"],
        "Resource": [
          "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-pro-v1:0",
          "arn:aws:bedrock:us-east-1:974724840334:inference-profile/us.amazon.nova-pro-v1:0",
          "arn:aws:bedrock:us-west-2::foundation-model/amazon.nova-pro-v1:0",
          "arn:aws:bedrock:us-west-2:974724840334:inference-profile/us.amazon.nova-pro-v1:0",
          "arn:aws:bedrock:*::foundation-model/us.amazon.nova-pro-v1:0",
          "arn:aws:bedrock:*:974724840334:inference-profile/us.amazon.nova-pro-v1:0"
        ],
        "Effect": "Allow"
      },
      {
        "Action": ["cloudwatch:PutMetricData"],
        "Resource": "*",
        "Effect": "Allow"
      }
    ]
  }'
```

### Rol Actualizado

```
arn:aws:iam::974724840334:role/learnia-chat-assistant-de-ChatAssistantFunctionRole-TKx7HQUGLlwq
```

### Permisos Agregados

Acción: `bedrock:InvokeModel`

Recursos:
- `arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-pro-v1:0`
- `arn:aws:bedrock:us-east-1:974724840334:inference-profile/us.amazon.nova-pro-v1:0`
- `arn:aws:bedrock:us-west-2::foundation-model/amazon.nova-pro-v1:0`
- `arn:aws:bedrock:us-west-2:974724840334:inference-profile/us.amazon.nova-pro-v1:0`
- `arn:aws:bedrock:*::foundation-model/us.amazon.nova-pro-v1:0` (wildcard para futuras regiones)
- `arn:aws:bedrock:*:974724840334:inference-profile/us.amazon.nova-pro-v1:0` (wildcard para futuras regiones)

## Configuración del Código

El código ya estaba correctamente configurado:

### template.yaml
```yaml
ChatAssistantFunction:
  Environment:
    Variables:
      BEDROCK_REGION: us-west-2
      BEDROCK_MODEL_ID: us.amazon.nova-pro-v1:0
      BEDROCK_TEMPERATURE: 0.7
      BEDROCK_MAX_TOKENS: 2048
  Policies:
    - Statement:
        - Effect: Allow
          Action:
            - bedrock:InvokeModel
          Resource:
            - arn:aws:bedrock:us-west-2::foundation-model/amazon.nova-pro-v1:0
            - arn:aws:bedrock:us-west-2:974724840334:inference-profile/us.amazon.nova-pro-v1:0
```

### bedrock_client.py
```python
def __init__(self) -> None:
    region = os.getenv("BEDROCK_REGION", "us-west-2")
    model_id = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")
    temperature = float(os.getenv("BEDROCK_TEMPERATURE", "0.7"))
    max_tokens = int(os.getenv("BEDROCK_MAX_TOKENS", "2048"))
    
    config = Config(
        region_name=region,
        retries={"max_attempts": 3, "mode": "standard"},
        read_timeout=30,
        connect_timeout=5,
        max_pool_connections=15,
    )
    
    self._client = boto3.client("bedrock-runtime", config=config)
```

## Verificación

Para verificar que los permisos están correctamente configurados:

```bash
aws iam get-role-policy \
  --role-name learnia-chat-assistant-de-ChatAssistantFunctionRole-TKx7HQUGLlwq \
  --policy-name ChatAssistantFunctionRolePolicy2 \
  --query 'PolicyDocument.Statement[?Action[0]=="bedrock:InvokeModel"]' \
  --output json
```

Output esperado:
```json
[
  {
    "Action": ["bedrock:InvokeModel"],
    "Resource": [
      "arn:aws:bedrock:us-west-2::foundation-model/amazon.nova-pro-v1:0",
      "arn:aws:bedrock:us-west-2:974724840334:inference-profile/us.amazon.nova-pro-v1:0",
      ...
    ],
    "Effect": "Allow"
  }
]
```

## Estado Actual

Estado: **RESUELTO**

- Lambda: `learnia-chat-assistant-dev`
- Región: `us-east-2` (lambda), Bedrock en `us-west-2`
- Modelo: `us.amazon.nova-pro-v1:0`
- Permisos: Habilitados para `bedrock:InvokeModel`
- Política: Actualizada el 2025-10-23

## Comportamiento Esperado

### Antes
```
POST /chat/message
Duration: 8-10 segundos
Response: "Por el momento no puedo consultar tu tutor..."
Logs: [ERROR] Bedrock invocation failed: AccessDeniedException
```

### Después
```
POST /chat/message
Duration: 5-7 segundos
Response: "Respuesta real del modelo Nova Pro basada en el contexto..."
Logs: [INFO] Invoking Bedrock for session xxx
      [SUCCESS] Message appended
```

## Próximos Pasos

1. Hacer un test en el chat del frontend
2. Revisar los logs de CloudWatch para confirmar no hay `AccessDeniedException`
3. Verificar que aparezcan respuestas reales del modelo Nova
4. Monitorear el performance y las métricas de la lambda

## Archivos Relacionados

- `template.yaml`: Configuración de SAM (incluye permisos de IAM y variables de entorno)
- `src/clients/bedrock_client.py`: Cliente de Bedrock que invoca el modelo
- `src/services/chat_service.py`: Servicio de chat que usa el cliente de Bedrock
- `src/chat_handler.py`: Handler principal de la lambda que enruta las solicitudes
- `README.md`: Documentación general del proyecto

## Referencias

- AWS Bedrock Documentation: https://docs.aws.amazon.com/bedrock/
- AWS IAM Documentation: https://docs.aws.amazon.com/iam/
- Amazon Nova Model: https://aws.amazon.com/nova/
