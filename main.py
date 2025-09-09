from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routers import math_generation
from app.database import engine
from app.models import Base
# Import all models to ensure they are registered with Base.metadata
import app.models.worksheet
import app.models.problem
import app.models.math_generation
import app.models.grading_result

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Math Problem Generation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "file://", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(math_generation.router, prefix="/api/math-generation", tags=["math-generation"])

@app.get("/")
async def root():
    return {"message": "Math Problem Generation API is running"}