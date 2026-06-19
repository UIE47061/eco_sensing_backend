import os
import secrets

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from routers import sensors, supabase_test
from util.config import Env

security = HTTPBasic()

app = FastAPI(
    title=Env.PROJECT_NAME,
    description="Eco sensing backend API",
    version=Env.VERSION,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def get_docs_credentials() -> tuple[str, str]:
    return (
        os.getenv("DOCS_USERNAME", Env.DOCS_USERNAME),
        os.getenv("DOCS_PASSWORD", Env.DOCS_PASSWORD),
    )


def verify_credentials(
    credentials: HTTPBasicCredentials = Depends(security),
) -> HTTPBasicCredentials:
    docs_username, docs_password = get_docs_credentials()
    if not docs_username or not docs_password:
        raise HTTPException(
            status_code=500,
            detail="Docs credentials are not configured",
        )

    is_valid_username = secrets.compare_digest(credentials.username, docs_username)
    is_valid_password = secrets.compare_digest(credentials.password, docs_password)
    if not (is_valid_username and is_valid_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials


@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint(
    credentials: HTTPBasicCredentials = Depends(verify_credentials),
):
    return get_openapi(title=Env.PROJECT_NAME, version=Env.VERSION, routes=app.routes)


@app.get("/docs", include_in_schema=False)
async def get_swagger_documentation(
    credentials: HTTPBasicCredentials = Depends(verify_credentials),
):
    return get_swagger_ui_html(openapi_url="/openapi.json", title=Env.PROJECT_NAME)


@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation(
    credentials: HTTPBasicCredentials = Depends(verify_credentials),
):
    return get_redoc_html(openapi_url="/openapi.json", title=Env.PROJECT_NAME)


origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://huggingface.co",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": f"Welcome to {Env.PROJECT_NAME}!", "status": "running"}


@app.get("/health")
def health_check() -> dict[str, object]:
    docs_username, docs_password = get_docs_credentials()
    return {
        "status": "ok",
        "docs_configured": bool(docs_username and docs_password),
    }


app.include_router(sensors.router)
app.include_router(supabase_test.router)


if __name__ == "__main__":
    port = int(os.getenv("PORT", str(Env.PORT)))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
