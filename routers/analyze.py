from fastapi import APIRouter
import pandas as pd
import os

router = APIRouter(prefix="/api/analyze", tags=["Analyze"])

# -------------------------------
#  Функция для вычисления рейтинга
# -------------------------------
def calc_rating(row):
    name = str(row.get("name") or "").lower()
    category = str(row.get("category") or "").lower()
    score = 5

    # Тематические слова, повышающие рейтинг
    if any(k in name for k in ["глэмпинг", "camp", "glamp", "кемпинг", "турбаза"]):
        score += 3
    if any(k in name for k in ["eco", "эко"]):
        score += 1
    if any(k in name for k in ["mountain", "гора", "altai", "shymbulak"]):
        score += 1
    if any(k in name for k in ["lux", "люкс", "премиум"]):
        score += 2
    if any(k in category for k in ["resort", "отель", "гостиница"]):
        score += 1

    return min(score, 10)


# -------------------------------
#  Функция для расчёта метрик
# -------------------------------
def calc_metrics(row):
    """Улучшенные метрики с балансом — чтобы не все были холодными"""
    metrics = {}

    name = str(row.get("name") or "").lower()
    category = str(row.get("category_type") or "").lower()

    # === 1. Активность в сети ===
    social = str(row.get("social") or "") + " " + str(row.get("website") or "")
    metrics["activity_score"] = 1 if any(s in social for s in ["instagram", "facebook", "vk", "site"]) else 0

    # === 2. Полнота данных ===
    completeness_fields = ["contacts", "address", "description", "photos"]
    filled = sum(1 for f in completeness_fields if str(row.get(f) or "").strip())
    metrics["completeness_score"] = round((filled / len(completeness_fields)) * 2, 2)  # 0–2

    # === 3. Популярность (рейтинг и отзывы) ===
    rating_val = float(row.get("rating_value") or 0)
    reviews = int(row.get("reviews_count") or 0)
    if rating_val >= 4 and reviews >= 10:
        metrics["popularity_score"] = 2
    elif rating_val >= 3.5 and reviews >= 3:
        metrics["popularity_score"] = 1
    else:
        metrics["popularity_score"] = 0.3

    # === 4. Вместимость / цена ===
    capacity = int(row.get("rooms") or 0)
    price = float(row.get("price_avg") or 0)
    if capacity >= 20 or price >= 20000:
        metrics["capacity_score"] = 2
    elif capacity >= 10 or price >= 10000:
        metrics["capacity_score"] = 1
    else:
        metrics["capacity_score"] = 0.3

    # === 5. Ниша  ===
    niche_bonus = {
        "люкс": 2,
        "эко": 1.8,
        "семейный": 1.5,
        "горный": 1.5,
        "этно": 1.2,
        "стандарт": 0.8,
    }
    metrics["target_score"] = niche_bonus.get(category, 1)

    # === 6. Коммерческий потенциал ===
    metrics["commercial_score"] = round(
        (metrics["completeness_score"] * 0.25 +
         metrics["activity_score"] * 0.25 +
         metrics["popularity_score"] * 0.25 +
         metrics["target_score"] * 0.25), 2
    )

    # === 7. Финальный рейтинг ===
    weights = {
        "activity_score": 0.15,
        "completeness_score": 0.2,
        "popularity_score": 0.2,
        "capacity_score": 0.15,
        "target_score": 0.15,
        "commercial_score": 0.15,
    }

    weighted_sum = sum(metrics[m] * w for m, w in weights.items())
    total = round(weighted_sum * 6, 1) 
    metrics["final_rating"] = min(total, 10)

    # === 8. Срочность ===
    if total >= 7.5:
        metrics["urgency"] = "🔥 Горячий лид"
    elif total >= 5:
        metrics["urgency"] = "🟡 Тёплый лид"
    else:
        metrics["urgency"] = "❄️ Холодный лид"

    return pd.Series(metrics)



# -------------------------------
#  Определение типа категории
# -------------------------------
def detect_category(cat):
    """
     Преобразует исходную категорию объекта в стандартный сегмент:
     Эко / Этно / Люкс / Семейный / Горный / Стандарт
     """
    cat = str(cat or "").lower()
    if any(k in cat for k in ["эко", "eco"]):
        return "Эко"
    elif any(k in cat for k in ["юрта", "этно"]):
        return "Этно"
    elif any(k in cat for k in ["глэмпинг", "lux", "люкс", "премиум"]):
        return "Люкс"
    elif any(k in cat for k in ["гостевой", "семейный"]):
        return "Семейный"
    elif any(k in cat for k in ["гора", "mountain"]):
        return "Горный"
    else:
        return "Стандарт"


# -------------------------------
#  Основной маршрут анализа
# -------------------------------
@router.get("/")
def analyze_data():
    """
     Основная функция обработки:
     1. Загружает исходный CSV-файл с объектами.
     2. Применяет фильтры по последнему запросу и городу.
     3. Вычисляет рейтинги, категории и метрики.
     4. Сохраняет результирующий CSV в /data/processed.
     """
    input_file = "data/raw/places.csv"
    output_file = "data/processed/analyzed.csv"
    query_file = "data/meta/last_query.txt"
    city_file = "data/meta/last_city.txt"

    if not os.path.exists(input_file):
        return {"error": f"Файл {input_file} не найден. Сначала запусти /api/places."}

    df = pd.read_csv(input_file)
    if df.empty:
        return {"warning": "Файл пуст, нет данных для анализа."}

    # Загружаем последний запрос
    current_query = ""
    if os.path.exists(query_file):
        with open(query_file, "r", encoding="utf-8") as f:
            current_query = f.read().strip().lower()

    # Загружаем последний город
    current_city = ""
    if os.path.exists(city_file):
        with open(city_file, "r", encoding="utf-8") as f:
            current_city = f.read().strip().lower()

    # Фильтрация по запросу
    if "query" in df.columns and current_query:
        df = df[df["query"].str.lower() == current_query]

    # Тематическая фильтрация
    theme_keywords = ["глэмпинг", "кемпинг", "турбаза", "отдых", "camp", "glamp", "resort"]
    if current_query:
        theme_keywords.append(current_query)
    df = df[df["name"].str.lower().apply(lambda x: any(k in x for k in theme_keywords))]

    # Расчёт рейтинга и метрик
    df["rating"] = df.apply(calc_rating, axis=1)
    df["category_type"] = df["category"].apply(detect_category)
    metrics_df = df.apply(calc_metrics, axis=1)
    df = pd.concat([df, metrics_df], axis=1)

    # Очистка данных
    df = df.drop_duplicates(subset=["name", "address"])
    df = df.dropna(subset=["name"])
    df = df[df["name"].str.strip() != ""]

    #  Фильтр по городу (динамический)
    if "city" in df.columns and current_city:
        df = df[df["city"].str.lower() == current_city]

    #  Топ-5 по рейтингу
    df = df.sort_values(by="rating", ascending=False).head(5)

    df = df.fillna("")
    os.makedirs("data/processed", exist_ok=True)
    df.to_csv(output_file, index=False)

    print(f"📊 Анализ завершён: {len(df)} объектов сохранено в {output_file}")
    print(f"🗂 Тема анализа: {current_query or 'не указана'} | Город: {current_city or 'не указан'}")

    return {
        "status": "done",
        "query": current_query,
        "city": current_city,
        "count": len(df),
        "output": output_file,
        "sample": df.head(3).to_dict(orient="records")
    }

