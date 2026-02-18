from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.api.v1 import documents, chat, auth
from app.core.config import settings
from app.core.logging_config import setup_logging
import os
import sys

print(f"DEBUG: Python Executable: {sys.executable}")
print(f"DEBUG: sys.path: {sys.path[:3]}")

app = FastAPI(title=settings.PROJECT_NAME)

# Middleware
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

from app.db.base import Base
from app.db.session import engine
Base.metadata.create_all(bind=engine)


app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])

@app.get("/")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/chat")
async def chat_page(request: Request):
    
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/signup")
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app.get("/verify-otp")
async def verify_otp_page(request: Request):
    return templates.TemplateResponse("verify_otp.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.INDEX_PATH, exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=8000)
