"""server_app.py — Factoría compartida de la aplicación FastAPI.

Ambos servidores (local `audioclass_server.py` y Colab
`audioclass_colab_server_v91.py`) construyen su app sobre esta base para no
duplicar la configuracion de CORS ni los metadatos. La autenticacion por API
key y el rate-limit permanecen en cada servidor porque difieren ligeramente
según el despliegue.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_base_app(title: str, description: str, version: str = "9.1.0") -> FastAPI:
    """Crea la app FastAPI con CORS ya configurado.

    Args:
        title: Titulo de la API (documentacion OpenAPI).
        description: Descripcion de la API.
        version: Version de la API.

    Returns:
        FastAPI: aplicacion lista para registrar rutas y middlewares propios.
    """
    app = FastAPI(title=title, description=description, version=version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app
