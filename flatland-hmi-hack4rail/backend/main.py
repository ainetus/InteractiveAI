from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import router

middleware_config = {
    "allow_origins": [
        "http://localhost:4200",
    ],
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    **middleware_config
)

app.include_router(router)
