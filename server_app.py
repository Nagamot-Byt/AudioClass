"""server_app.py — Factoría compartida de la aplicación FastAPI.

Ambos servidores (local `audioclass_server.py` y Colab
`audioclass_colab_server_v91.py`) construyen su app sobre esta base para no
duplicar la configuracion de CORS ni los metadatos. La autenticacion por API
key y el rate-limit permanecen en cada servidor porque difieren ligeramente
según el despliegue.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

_DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
    "https://colab.research.google.com",
]

_DEFAULT_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1|.*\.ngrok-free\.app|.*\.ngrok\.io)(:\d+)?$"


def create_base_app(
    title: str,
    description: str,
    version: str = "9.1.0",
    allowed_origins: list[str] | None = None,
) -> FastAPI:
    """Crea la app FastAPI con CORS configurado de forma segura y compatible con W3C.

    Args:
        title: Titulo de la API (documentacion OpenAPI).
        description: Descripcion de la API.
        version: Version de la API.
        allowed_origins: Lista opcional de orígenes permitidos. Si no se especifica,
            se lee de la variable de entorno AUDIOCLASS_ALLOWED_ORIGINS o se usan los
            defaults seguros (localhost, 127.0.0.1, Google Colab y túneles ngrok).

    Returns:
        FastAPI: aplicacion lista para registrar rutas y middlewares propios.
    """
    app = FastAPI(title=title, description=description, version=version)

    env_origins = os.environ.get("AUDIOCLASS_ALLOWED_ORIGINS", "")
    if allowed_origins is not None:
        origins = allowed_origins
    elif env_origins.strip():
        origins = [o.strip() for o in env_origins.split(",") if o.strip()]
    else:
        origins = _DEFAULT_ALLOWED_ORIGINS

    # Si se permite wildcard '*', allow_credentials DEBE ser False según la spec W3C
    has_wildcard = "*" in origins
    allow_credentials = not has_wildcard

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=_DEFAULT_ORIGIN_REGEX if not has_wildcard else None,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    return app
