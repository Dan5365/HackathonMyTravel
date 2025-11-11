from fastapi import FastAPI

from routers import places, analyze, generate, stats
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(title="MyTravel API")

# uvicorn main:app --reload
# taskkill /IM python.exe /F
@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}

app.include_router(places.router)
app.include_router(analyze.router)
app.include_router(generate.router)

app.include_router(stats.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)