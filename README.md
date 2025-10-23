# LearnIA Chat Assistant Lambda

Lambda responsable de manejar el chat contextual de LearnIA. El asistente actúa como tutor personalizado basado en la ruta de aprendizaje seleccionada por el usuario, manteniendo las conversaciones históricas en DynamoDB y apoyándose en Bedrock Nova para generar respuestas.

## Arquitectura

- **API Gateway**: expone los endpoints REST `/chat/message`, `/chat/history/{session_id}`, `/chat/sessions` y `/chat/session/{session_id}`.
- **Lambda**: `chat_handler.lambda_handler` enruta las peticiones hacia los servicios correspondientes.
- **DynamoDB**: tabla `learnia-chat-sessions-<env>` almacena el historial de mensajes (TTL automático).
- **PostgreSQL (RDS)**: fuente de verdad para rutas de aprendizaje y progreso de cursos del usuario.
- **MongoDB Atlas**: se consulta de forma opcional para enriquecer la metadata de cursos.
- **Amazon Bedrock**: modelo Nova Pro genera las respuestas en español con el contexto del usuario.
- **CloudWatch**: centraliza logs y métricas personalizadas.

## Estructura

```
chat-assistant-lambda/
├── template.yaml
├── README.md
├── requirements.txt
└── src/
    ├── chat_handler.py
    ├── clients/
    │   ├── bedrock_client.py
    │   ├── dynamodb_client.py
    │   └── postgres_client.py
    ├── services/
    │   ├── chat_service.py
    │   └── context_builder.py
    └── utils/
        ├── http.py
        └── auth.py
```

## Endpoints

| Método | Path                      | Descripción                                                                 |
|--------|--------------------------|-----------------------------------------------------------------------------|
| POST   | `/chat/message`          | Envía un mensaje al asistente. Crea sesión si no existe.                    |
| GET    | `/chat/history/{id}`     | Obtiene los últimos mensajes de la sesión indicada.                         |
| GET    | `/chat/sessions`         | Lista las sesiones activas para el usuario actual y ruta especificada.      |
| DELETE | `/chat/session/{id}`     | Elimina una sesión y todo su historial.                                     |

## Variables de entorno clave

| Nombre                | Descripción                                               |
|-----------------------|-----------------------------------------------------------|
| `CHAT_SESSIONS_TABLE` | Nombre de la tabla DynamoDB para historial de chats.      |
| `SESSION_TTL_DAYS`    | Días antes de que la sesión expire automáticamente.       |
| `MAX_HISTORY_MESSAGES`| Mensajes anteriores que se usan para el contexto.         |
| `BEDROCK_MODEL_ID`    | ID del modelo de Bedrock (default `us.amazon.nova-pro-v1:0`). |

## Despliegue

```
sam build
sam deploy --guided
```

> Nota: necesitarás proveer los parámetros `AtlasUri`, `PostgresHost`, `PostgresPassword` y el `CorsAllowOrigin` si difiere del dominio por defecto.

## Desarrollo local

1. Crear entorno virtual y resolver dependencias:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Configurar variables de entorno (por ejemplo via `.env`) para Bedrock, DynamoDB local y conexiones a bases de datos.
3. Ejecutar pruebas unitarias:
   ```bash
   pytest
   ```

## Próximos pasos

- Agregar soporte para respuestas streaming (eventos SSE) de Nova.
- Integrar analíticas de uso (conteo de consultas por ruta / usuario).
- Añadir rate limiting por usuario directamente en la lambda para complementar API Gateway.
