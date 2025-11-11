from fastapi import APIRouter
import pandas as pd
import os

router = APIRouter(prefix="/api/export", tags=["Export"])


@router.get("/")
def export_data():
    file_path = "data/processed/final.csv"
    if not os.path.exists(file_path):
        return {"error": "Файл final.csv не найден. Сначала запусти /api/generate."}

    df = pd.read_csv(file_path)
    return df.to_dict(orient="records")
