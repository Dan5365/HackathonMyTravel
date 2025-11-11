# routers/places.py
from fastapi import APIRouter
import requests
import os
import pandas as pd
import json
import math
from dotenv import load_dotenv

load_dotenv()
router = APIRouter(prefix="/api/places", tags=["Places"])

API_KEY = os.getenv("DGIS_API_KEY", "401b0774-dbe8-4f70-91c9-697adac3e650")

DATA_DIR = "data/raw"
META_DIR = "data/meta"
FILE_PATH = os.path.join(DATA_DIR, "places.csv")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(META_DIR, exist_ok=True)


# --- Utility functions ---
def safe_float(v):
    try:
        v = float(v)
        if math.isnan(v) or math.isinf(v):
            return None
        return round(v, 6)
    except:
        return None


def extract_contacts(contact_groups):
    """
    Извлекает телефоны, сайты и соцсети из блока contacts
    """
    if not contact_groups:
        return "", ""

    phones, socials = [], []
    for group in contact_groups:
        for contact in group.get("contacts", []):
            ctype = contact.get("type", "")
            value = contact.get("value", "")

            if ctype == "phone" and value:
                phones.append(value)

            elif ctype == "website" and value:
                socials.append(value)

            elif ctype == "link" and value:
                lower = value.lower()
                if any(net in lower for net in ["instagram", "facebook", "vk", "t.me", "telegram", "whatsapp"]):
                    socials.append(value)

    return ", ".join(phones), ", ".join(socials)

def fetch_contacts_by_id(item_id):
    """Дополнительный запрос, если contact_groups пустой"""
    url = "https://catalog.api.2gis.com/3.0/items/byid"
    params = {"id": item_id, "key": API_KEY, "fields": "items.contact_groups"}
    resp = requests.get(url, params=params).json()
    items = resp.get("result", {}).get("items", [])
    if not items:
        return "", ""
    return extract_contacts(items[0].get("contact_groups"))


def extract_coords(point):
    if not point:
        return "", None, None
    lat, lon = safe_float(point.get("lat")), safe_float(point.get("lon"))
    coords = f"{lat}, {lon}" if lat and lon else ""
    return coords, lat, lon


def extract_schedule(item):
    s = item.get("schedule")
    if not s:
        return ""
    try:
        return json.dumps(s, ensure_ascii=False)
    except:
        return str(s)


def get_region_id(city: str):
    """Определяем регион через Regions API (только Казахстан)"""
    url = "https://catalog.api.2gis.com/2.0/region/search"
    params = {"q": city, "key": API_KEY}
    resp = requests.get(url, params=params).json()

    items = resp.get("result", {}).get("items", [])
    for i in items:
        # Ищем только в Казахстане
        if "Казахстан" in i.get("full_name", "") or "Kazakhstan" in i.get("full_name", ""):
            return i.get("id")
    # Если не нашли — fallback
    return items[0]["id"] if items else None


@router.get("/")
def get_places(query: str = "Магазин", city: str = "Астана"):
    """Поиск компаний/мест в 2GIS по названию и городу (с автоматическим region_id)"""

    region_id = get_region_id(city)
    if not region_id:
        return {"error": f"❌ Не найден регион для города '{city}'"}

    print(f"🌍 Найден регион '{city}' → ID: {region_id}")

    url = "https://catalog.api.2gis.com/3.0/items"
    params = {
        "q": query,
        "region_id": region_id,
        "key": API_KEY,
        "page_size": 50,
        "locale": "ru_KZ",
        "fields": "items.contact_groups,items.address_name,items.rubrics,items.point,items.schedule"
    }

    resp = requests.get(url, params=params).json()

    if resp.get("meta", {}).get("code") != 200:
        return {"error": "Ошибка при обращении к Places API", "details": resp.get("meta")}

    items = resp.get("result", {}).get("items", [])
    if not items:
        return {"status": "no_results", "query": query, "city": city}

    results = []
    for item in items:
        if item.get("type") not in ["branch", "firm"]:
            continue
        coords, lat, lon = extract_coords(item.get("point"))
        phones, socials = extract_contacts(item.get("contact_groups"))
        results.append({
            "name": item.get("name", ""),
            "address": item.get("address_name", ""),
            "contacts": phones,
            "social": socials,
            "coords": coords,
            "category": item.get("rubrics")[0]["name"] if item.get("rubrics") else "",
            "lat": lat,
            "lon": lon,
            "schedule": extract_schedule(item),
            "query": query,
            "city": city
        })

    # --- merge and save ---
    new_df = pd.DataFrame(results)
    if os.path.exists(FILE_PATH):
        try:
            old_df = pd.read_csv(FILE_PATH)
        except:
            old_df = pd.DataFrame()
        combined = pd.concat([old_df, new_df], ignore_index=True).drop_duplicates(subset=["name", "address"])
    else:
        combined = new_df

    combined.replace([float("inf"), -float("inf"), None], "", inplace=True)
    combined.to_csv(FILE_PATH, index=False, encoding="utf-8")

    # --- save meta ---
    with open(os.path.join(META_DIR, "last_query.txt"), "w", encoding="utf-8") as f:
        f.write(query)
    with open(os.path.join(META_DIR, "last_city.txt"), "w", encoding="utf-8") as f:
        f.write(city)

    # --- filter sample for current request ---
    filtered_sample = combined[
        (combined["query"] == query) & (combined["city"] == city)
    ].tail(3)

    print(f"✅ {len(new_df)} новых объектов ({city})")

    return {
        "status": "success",
        "query": query,
        "city": city,
        "region_id": region_id,
        "count_new": len(new_df),
        "total_saved": len(combined),
        "file": FILE_PATH,
        "sample": filtered_sample.to_dict(orient="records")
    }
