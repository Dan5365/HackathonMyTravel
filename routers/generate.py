# routers/generate.py
from fastapi import APIRouter
import os, asyncio, time, json, re
from dotenv import load_dotenv
import pandas as pd
import google.generativeai as genai
from datetime import datetime

load_dotenv()
router = APIRouter(prefix="/api/generate", tags=["AI Descriptions"])
genai.configure(api_key=os.getenv("GEMINI_API_KEY", "AIzaSyDT7vLvYPpM_qJ6U3fEskxmIMKizl3uwDk"))

INPUT_FILE = "data/processed/analyzed.csv"
OUTPUT_FILE = "data/processed/final.csv"

# -------------------------------------------------------------------
#  Генерация описания с требуемым JSON-форматом
# -------------------------------------------------------------------
async def generate_extended_description(model, name, category, address, niche, index, total):
    """
     Генерирует три текстовых поля для карточки места:
       - seo_title
       - short_description
       - description

     Работает с Google Gemini, обрабатывает ошибки и пытается извлечь JSON.
     """


    prompt = f"""
Ты — опытный копирайтер туристического сервиса. 
Создай уникальные тексты для карточки места «{name}».

Выведи строго в формате JSON:
{{
  "seo_title": "Короткий SEO-заголовок (до 80 символов, без кавычек)",
  "short_description": "1–2 предложения (до 200 символов), живое описание без шаблонных фраз",
  "description": "Развёрнутое описание (150–300 слов), интересное, эмоциональное, подходящее для сайта"
}}

Контекст:
- Название: {name}
- Категория: {category or "не указана"}
- Адрес: {address or "не указан"}
- Ниша: {niche or "общая туризм/отдых"}

Требования:
- Избегай одинаковых выражений между объектами (например: "вдали от городской суеты", "откройте для себя", "уютный уголок").
- Каждый текст должен звучать по-разному: меняй стиль, ритм и лексику.
- Передай атмосферу через детали (что человек чувствует, видит, слышит в этом месте).
- Не используй шаблонные обороты и рекламные клише.
- Стиль: естественный, человечный, с лёгкими эмоциями, но без пафоса.
- Можно слегка менять тональность: романтичный, приключенческий, семейный, деловой — если подходит категории.
- Не упоминай процесс генерации или сайт.

"""


    for attempt in range(3):
        try:
            print(f"🔹 [{index}/{total}] Генерация: {name} (попытка {attempt + 1})")

            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config={"max_output_tokens": 800}
            )
            text = getattr(response, "text", "").strip()

            # --- Пытаемся извлечь JSON из текста ---
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                   
                    return {
                        "title": data.get("seo_title", "").strip(),
                        "short": data.get("short_description", "").strip(),
                        "description": data.get("description", "").strip()
                    }
                except Exception:
                    pass

            # --- fallback: вытаскиваем вручную ---
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            title = lines[0][:80] if lines else ""
            short = lines[1][:200] if len(lines) > 1 else ""
            desc = " ".join(lines[2:]) if len(lines) > 2 else text
            return {"title": title, "short": short, "description": desc}
        except Exception as e:
            print(f"⚠️ Ошибка у {name}: {e}")
            if "429" in str(e).lower():
                await asyncio.sleep(2 * (attempt + 1))
                continue
    return {"title": "", "short": "", "description": "Ошибка при генерации."}


# -------------------------------------------------------------------
#  Основной эндпоинт: генерация описаний
# -------------------------------------------------------------------
@router.get("/")
async def generate_descriptions(limit: int = 5):
    if not os.path.exists(INPUT_FILE):
        return {"error": f"Файл {INPUT_FILE} не найден. Сначала запусти /api/analyze."}

    print("\n🚀 [START] Генерация описаний через Gemini...")
    start_time = time.time()

    df = pd.read_csv(INPUT_FILE).head(limit)
    if df.empty:
        return {"warning": "Нет данных для генерации."}

    model = genai.GenerativeModel("gemini-2.5-flash-lite")

    tasks = [
        generate_extended_description(
            model,
            row.get("name", "Туристический объект"),
            row.get("category_type", "Размещение"),
            row.get("address", "Казахстан"),
            row.get("niche", "Экотуризм"),
            i + 1, len(df)
        )
        for i, row in df.iterrows()
    ]

    results = await asyncio.gather(*tasks)

    df["seo_title"] = [r["title"] for r in results]
    df["short_description"] = [r["short"] for r in results]
    df["description"] = [r["description"] for r in results]

    os.makedirs("data/processed", exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")

    elapsed = round(time.time() - start_time, 2)
    print(f"✅ Завершено за {elapsed} секунд. Файл сохранён: {OUTPUT_FILE}")

    return {
        "status": "done",
        "count": len(df),
        "output": OUTPUT_FILE,
        "time_sec": elapsed,
        "sample": df[["name", "seo_title", "short_description"]].head(2).to_dict(orient="records")
    }


# -------------------------------------------------------------------
# Генерация шаблонов сообщений (Outreach)
# -------------------------------------------------------------------

@router.get("/outreach")
async def generate_outreach_template(name: str, niche: str, location: str, channel: str = "email"):
    model = genai.GenerativeModel("gemini-2.5-flash-lite")
    prompt = f"""
Ты — маркетолог mytravel.kz. Составь персонализированное сообщение для первого контакта.

Формат:
{{
  "greeting": "Приветствие",
  "body": "Основной текст с пользой и CTA",
  "signature": "Команда mytravel.kz"
}}

Канал: {channel}
Название: {name}
Локация: {location}
Ниша: {niche}

Пример CTA: "Хотим добавить вас в каталог. Можно поговорить?"
Пиши естественно и дружелюбно.
"""

    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        text = getattr(response, "text", "")
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return data
    except Exception as e:
        return {"error": str(e)}

    return {"greeting": "Привет!", "body": "Мы заметили ваш объект и хотим сотрудничать.", "signature": "Команда mytravel.kz"}

@router.get("/outreach_ab")
async def generate_outreach_ab(name: str, niche: str, location: str):
    """
    Генерирует два разных шаблона (A и B) для A/B теста.
    """
    model = genai.GenerativeModel("gemini-2.5-flash-lite")

    variants = []
    for variant in ["A", "B"]:
        prompt = f"""
        Ты — маркетолог mytravel.kz.
        Составь версию {variant} шаблона первого контакта.

        Формат:
        {{
          "variant": "{variant}",
          "greeting": "Приветствие",
          "body": "Основной текст с пользой и CTA",
          "signature": "Команда mytravel.kz"
        }}

        Название: {name}
        Локация: {location}
        Ниша: {niche}
        """

        response = await asyncio.to_thread(model.generate_content, prompt)
        text = getattr(response, "text", "")
        match = re.search(r"\{.*\}", text, re.DOTALL)
        data = json.loads(match.group(0)) if match else {"variant": variant, "body": text}
        variants.append(data)

    # сохраняем для анализа
    os.makedirs("data", exist_ok=True)
    with open("data/outreach_tests.json", "w", encoding="utf-8") as f:
        json.dump(variants, f, ensure_ascii=False, indent=2)

    return {"status": "done", "variants": variants}

