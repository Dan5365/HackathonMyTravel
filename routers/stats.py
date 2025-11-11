# routers/stats.py
from fastapi import APIRouter
import pandas as pd
import os

router = APIRouter(prefix="/api/stats", tags=["Statistics"])

@router.get("/getstats")
def get_stats():
    """
    Генерирует сводную статистику по анализу лидов:
    - количество объектов
    - распределение по нишам
    - доля горячих/тёплых/холодных лидов
    """
    file_path = "data/processed/analyzed.csv"
    if not os.path.exists(file_path):
        return {"error": "Файл не найден. Сначала запусти /api/analyze."}

    df = pd.read_csv(file_path)
    if df.empty:
        return {"warning": "Файл пуст."}

    total = len(df)
    urgency_stats = df["urgency"].value_counts().to_dict()
    category_stats = df["category_type"].value_counts().to_dict()
    avg_rating = round(df["rating"].mean(), 2) if "rating" in df.columns else None

    return {
        "total_objects": total,
        "avg_rating": avg_rating,
        "urgency_distribution": urgency_stats,
        "category_distribution": category_stats,
        "top5": df.nlargest(5, "rating")[["name", "city", "rating", "urgency"]].to_dict(orient="records")
    }
