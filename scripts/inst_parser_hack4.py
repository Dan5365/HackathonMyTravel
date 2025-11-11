import os
import csv
import json
import time
import random
import math
from datetime import datetime, timedelta, timezone
from pydantic import ValidationError

from instagrapi import Client
from instagrapi.exceptions import UserNotFound
from instagrapi.types import Media, User, Location
from instagrapi.extractors import extract_media_v1

# --- НАСТРОЙКИ СКРИПТА ---
USERNAME = "USER"
PASSWORD = "Password"
SESSION_FILE = "instagram_sessions/my_instagram_session.json"
INPUT_CSV_FILE = "found_users.csv"
OUTPUT_CSV_FILE = "instagram_data_summary.csv"
OUTPUT_JSON_REPORT_FILE = "instagram_data_full_report.json"
POSTS_TO_FETCH = 10
CAPTION_TRUNCATE_LIMIT = 300


# --- НАСТРОЙКИ ПОИСКА ---
SEARCH_KEYWORDS = ["глэмпинг", "глэмпинг астана"]
SEARCH_CITY = "Астана" 
SEARCH_LIMIT_PER_QUERY = 30 
FOUND_USERS_CSV_FILE = "found_users.csv"



def human_delay(min_seconds=5, max_seconds=12):
    delay = random.uniform(min_seconds, max_seconds)
    print(f"⏳ Пауза на {delay:.2f} секунд...")
    time.sleep(delay)


def extract_hashtags(text: str) -> list:
    if not text: return []
    return [tag.strip("#") for tag in text.split() if tag.startswith("#")]


def calculate_metrics(posts: list, followers_count: int) -> dict:
    metrics = {"avg_likes": 0, "avg_comments": 0, "engagement_rate_percent": 0.0, "posting_frequency_days": None, "activity_score": 0.0}
    if not posts: return metrics
    
    num_posts = len(posts)
    metrics["avg_likes"] = sum(p.like_count for p in posts) / num_posts
    metrics["avg_comments"] = sum(p.comment_count for p in posts) / num_posts

    if followers_count > 0:
        metrics["engagement_rate_percent"] = ((metrics["avg_likes"] + metrics["avg_comments"]) / followers_count) * 100
    
    if num_posts > 1:
        posts_sorted = sorted(posts, key=lambda p: p.taken_at, reverse=True)
        time_diffs = [(posts_sorted[i].taken_at - posts_sorted[i+1].taken_at).total_seconds() for i in range(num_posts - 1)]
        metrics["posting_frequency_days"] = (sum(time_diffs) / len(time_diffs)) / 86400
    
    now = datetime.now(timezone.utc)
    posts_last_30_days = sum(1 for p in posts if p.taken_at > now - timedelta(days=30))
    score_posts = min(posts_last_30_days / 10, 1) * 5
    score_engagement = min(metrics["engagement_rate_percent"] / 5, 1) * 5
    metrics["activity_score"] = round(score_posts + score_engagement, 1)
    
    return metrics


def calculate_lead_analysis(profile_data: dict, calculated_metrics: dict) -> dict:
    followers = profile_data.get('followers_count', 0)
    popularity = round(min(math.log10(followers or 1) * 1.6, 10), 1)

    completeness_score = 0
    if profile_data.get('bio'): completeness_score += 3
    if profile_data.get('website'): completeness_score += 3
    if profile_data.get('is_business'): completeness_score += 2
    if profile_data.get('business_category'): completeness_score += 2
    data_completeness = float(completeness_score)
    
    er = calculated_metrics.get('engagement_rate_percent', 0.0)
    potential_score = 0
    potential_score += min(er / 2.5, 1) * 4
    if profile_data.get('is_business'): potential_score += 2
    if profile_data.get('website'): potential_score += 2
    potential_score += popularity / 10 * 2
    commercial_potential = round(potential_score, 1)

    network_activity = calculated_metrics.get('activity_score', 0.0)
    final_score = round((network_activity * 0.4) + (commercial_potential * 0.4) + (popularity * 0.1) + (data_completeness * 0.1), 1)
    
    if final_score >= 8.0: priority = "hot"
    elif final_score >= 5.0: priority = "medium"
    else: priority = "low"

    return {
        "network_activity": network_activity, "data_completeness": data_completeness,
        "popularity": popularity, "filling_potential": 10.0 - data_completeness,
        "target_audience_fit": None, "commercial_potential": commercial_potential,
        "final_score": final_score, "priority": priority
    }


def search_and_prepare_users(cl: Client, keywords: list, city: str, limit: int):
    if not keywords and not city:
        print("ℹ️ Ключевые слова и город для поиска не указаны. Пропускаем этап поиска.")
        return

    print("\n--- 🔍 НАЧАЛО ПОИСКА ПОЛЬЗОВАТЕЛЕЙ ---")
    found_users_data = {}

    if city:
        print(f"📍 Ищем пользователей по городу: {city}")
        try:
            
            locations = cl.location_search(city)
            if not locations:
                print(f"⚠️ Не удалось найти локацию для города '{city}'.")
            else:
                location = locations[0]
                print(f"  > Найдена локация: {location.name} (ID: {location.pk})")
                medias = cl.location_medias_top(location.pk, amount=limit)
                print(f"  > Найдено {len(medias)} популярных постов в этой локации.")
                for media in medias:
                    if not hasattr(media, 'user'): continue
                    user = media.user
                    if user.username not in found_users_data:
                         found_users_data[user.username] = {
                            "username": user.username, "full_name": user.full_name, "followers": "", "bio": "",
                            "city": city, "link": f"https://www.instagram.com/{user.username}/"
                        }
                human_delay(3, 7)
        except Exception as e:
            print(f"❌ Ошибка при поиске по городу '{city}': {e}")

    if keywords:
        for keyword in keywords:
            print(f"🔑 Ищем пользователей по ключевому слову: '{keyword}'")
            try:
                results = cl.search_users(keyword)[:limit]
                print(f"  > Найдено {len(results)} аккаунтов.")
                for user in results:
                    if user.username not in found_users_data:
                        
                        found_users_data[user.username] = {
                            "username": user.username, "full_name": user.full_name,
                            "followers": "", 
                            "bio": "",      
                            "city": "", "link": f"https://www.instagram.com/{user.username}/"
                        }
                human_delay(3, 7)
            except Exception as e:
                print(f"❌ Ошибка при поиске по ключевому слову '{keyword}': {e}")
    
    if not found_users_data:
        print("🤷‍♂️ Новых пользователей по заданным критериям не найдено.")
        print("--- 🏁 ПОИСК ЗАВЕРШЕН ---\n")
        return

    print(f"\n✅ Всего найдено уникальных пользователей: {len(found_users_data)}")
    found_users_list = list(found_users_data.values())
    
    try:
        with open(FOUND_USERS_CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["username", "full_name", "followers", "bio", "city", "link"])
            writer.writeheader()
            writer.writerows(found_users_list)
        print(f"💾 Результаты поиска сохранены в файл: {FOUND_USERS_CSV_FILE}")
    except Exception as e:
        print(f"❌ Не удалось сохранить результаты поиска в {FOUND_USERS_CSV_FILE}: {e}")

    try:
        existing_usernames = set()
        if os.path.exists(INPUT_CSV_FILE):
            with open(INPUT_CSV_FILE, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'username' in row:
                        existing_usernames.add(row['username'].strip())
        
        new_users_to_add = [ user for user in found_users_data.keys() if user not in existing_usernames ]
        if new_users_to_add:
            print(f"➕ Добавляем {len(new_users_to_add)} новых пользователей в {INPUT_CSV_FILE} для последующего анализа.")
            with open(INPUT_CSV_FILE, 'a', newline='', encoding='utf-8') as f:
                is_file_empty = os.stat(INPUT_CSV_FILE).st_size == 0
                writer = csv.DictWriter(f, fieldnames=['object_id', 'username'])
                if is_file_empty: writer.writeheader()
                for username in new_users_to_add:
                    writer.writerow({'object_id': '', 'username': username})
        else:
            print("👍 Все найденные пользователи уже присутствуют в файле для анализа.")
    except Exception as e:
        print(f"❌ Не удалось обновить файл {INPUT_CSV_FILE}: {e}")

    print("--- 🏁 ПОИСК ЗАВЕРШЕН ---\n")


def get_user_posts_robust(cl: Client, user_id: str, amount: int) -> list[Media]:
    posts = []
    try:
        
        response = cl.private_request(f'feed/user/{user_id}/', params={'count': amount})
        
      
        raw_medias = response.get('items', [])
        if not isinstance(raw_medias, list):
            print(f"  - ⚠️ Неожиданный формат ответа от API. Ключ 'items' не является списком.")
            return []

        for raw_media in raw_medias:
            try:
                
                posts.append(extract_media_v1(raw_media))
            except ValidationError as e:
                media_pk = raw_media.get('pk', 'N/A')
               
                error_msg = e.errors()[0]['msg'] if e.errors() else "Unknown validation error"
                print(f"  - ⚠️ Пропущен пост (ID: {media_pk}) из-за ошибки валидации: {error_msg}")
                continue 
    except Exception as e:
         print(f"  - ❌ Критическая ошибка при загрузке постов: {e}")
    return posts


def main():
    cl = Client()
  
    session_dir = os.path.dirname(SESSION_FILE)
    if session_dir: os.makedirs(session_dir, exist_ok=True)

    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE); cl.login(USERNAME, PASSWORD)
            print("✅ Вход выполнен с использованием сохраненной сессии.")
        except Exception:
            print("⚠️ Не удалось войти с сессией. Попытка входа по логину и паролю.")
            cl.login(USERNAME, PASSWORD); cl.dump_settings(SESSION_FILE)
            print("✅ Выполнен свежий вход, сессия сохранена.")
    else:
        print("ℹ️ Файл сессии не найден. Вход по логину и паролю.")
        cl.login(USERNAME, PASSWORD); cl.dump_settings(SESSION_FILE)
        print("✅ Вход выполнен, сессия сохранена.")

    search_and_prepare_users(cl, SEARCH_KEYWORDS, SEARCH_CITY, SEARCH_LIMIT_PER_QUERY)

    try:
        with open(INPUT_CSV_FILE, mode='r', encoding='utf-8') as f:
            non_empty_lines = (line for line in f if line.strip())
            users_to_process = list(csv.DictReader(non_empty_lines))
    except FileNotFoundError:
        print(f"❌ ОШИБКА: Входной файл '{INPUT_CSV_FILE}' не найден. Анализ невозможен.")
        return
    
    if not users_to_process:
        print(f"🤷‍♂️ Файл '{INPUT_CSV_FILE}' пуст. Некого анализировать.")
        return

    print(f"\n--- 🚀 НАЧАЛО ГЛУБОКОГО АНАЛИЗА ---")
    print(f"📈 Найдено {len(users_to_process)} пользователей для обработки.")

    csv_fieldnames = [
        'object_id', 'username', 'status', 'la_priority', 'la_final_score',
        'display_name', 'followers_count', 'following_count', 'posts_count', 
        'bio', 'website', 'is_business', 'business_category',
        'avg_likes', 'avg_comments', 'engagement_rate_percent', 'posting_frequency_days', 'activity_score',
        'la_network_activity', 'la_commercial_potential', 'la_popularity', 'la_data_completeness', 'la_filling_potential', 'la_target_audience_fit',
        'instagram_url'
    ]
    
    all_users_full_data = []
    
    with open(OUTPUT_CSV_FILE, 'w', newline='', encoding='utf-8') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=csv_fieldnames)
        writer.writeheader()

        for i, user_row in enumerate(users_to_process):
            username = user_row.get('username', '').strip()
            if not username: continue
            
            print(f"\n--- Анализ {i+1}/{len(users_to_process)}: {username} ---")
            
            result_row = {'object_id': user_row.get('object_id', ''), 'username': username, 'instagram_url': f"https://www.instagram.com/{username}/", 'status': 'ERROR'}

            try:
                user_info: User = cl.user_info_by_username_v1(username)
                
                profile_data = {
                    "username": user_info.username, "display_name": user_info.full_name,
                    "followers_count": user_info.follower_count, "following_count": user_info.following_count,
                    "posts_count": user_info.media_count, "bio": user_info.biography,
                    "website": str(user_info.external_url) if user_info.external_url else '',
                    "is_business": user_info.is_business, "business_category": getattr(user_info, 'category_name', '')
                }

                if user_info.is_private:
                    result_row['status'] = 'PRIVATE'; print("🔒 Профиль приватный.")
                    result_row.update(profile_data)
                    writer.writerow(result_row); human_delay(2, 5); continue
                
                result_row.update({'status': 'OK', **profile_data})
                
                print(f"📄 Загрузка последних {POSTS_TO_FETCH} постов...")
                
                recent_posts = get_user_posts_robust(cl, user_info.pk, POSTS_TO_FETCH)
                print(f"  > Успешно загружено {len(recent_posts)}/{POSTS_TO_FETCH} постов для анализа.")

                calculated_metrics = calculate_metrics(recent_posts, user_info.follower_count)
                
                calculated_metrics_rounded = {
                    'avg_likes': round(calculated_metrics.get('avg_likes', 0)),
                    'avg_comments': round(calculated_metrics.get('avg_comments', 0)),
                    'engagement_rate_percent': round(calculated_metrics.get('engagement_rate_percent', 0.0), 2),
                    'posting_frequency_days': round(calculated_metrics.get('posting_frequency_days', 0.0), 1) if calculated_metrics.get('posting_frequency_days') is not None else None,
                    'activity_score': calculated_metrics.get('activity_score', 0.0)
                }

                lead_analysis_data = calculate_lead_analysis(profile_data, calculated_metrics_rounded)
                print(f"⭐ Анализ лида: итоговый балл {lead_analysis_data.get('final_score')}, приоритет '{lead_analysis_data.get('priority')}'")
                
                result_row.update(calculated_metrics_rounded)
                result_row.update({f"la_{k}": v for k, v in lead_analysis_data.items()})
                
                posts_details = []
                for post in recent_posts:
                    media_urls = [r.thumbnail_url for r in post.resources] if post.media_type == 8 else ([post.thumbnail_url] if post.thumbnail_url else [])
                    posts_details.append({'post_id': post.pk, 'date': post.taken_at.isoformat(), 'caption': (post.caption_text or '')[:CAPTION_TRUNCATE_LIMIT], 'likes': post.like_count, 'comments': post.comment_count, 'media_urls': [str(url) for url in media_urls if url], 'has_location': bool(post.location), 'hashtags': extract_hashtags(post.caption_text), 'is_video': post.media_type == 2})
                
                all_users_full_data.append({
                    "profile_info": profile_data, "calculated_metrics": calculated_metrics_rounded,
                    "lead_analysis": lead_analysis_data, "recent_posts": posts_details
                })
                
                print(f"✅ Профиль {username} успешно обработан.")

            except UserNotFound:
                result_row['status'] = 'NOT_FOUND'; print(f"❓ Пользователь {username} не найден.")
            except Exception as e:
                result_row['status'] = 'ERROR'; print(f"❌ Непредвиденная ошибка при обработке {username}: {e}")
            
            writer.writerow(result_row)
            human_delay(8, 20)

    with open(OUTPUT_JSON_REPORT_FILE, 'w', encoding='utf-8') as json_file:
        json.dump(all_users_full_data, json_file, indent=4, ensure_ascii=False)

    print("\n🎉🎉🎉 Работа завершена! 🎉🎉🎉")
    print(f"🔍 Результаты поиска сохранены в: {FOUND_USERS_CSV_FILE}")
    print(f"📊 Сводные данные анализа сохранены в: {OUTPUT_CSV_FILE}")
    print(f"📄 Полный аналитический отчет сохранен в: {OUTPUT_JSON_REPORT_FILE}")


if __name__ == "__main__":
    if USERNAME == "your_instagram_username" or PASSWORD == "your_instagram_password":
        print("🔴 ВНИМАНИЕ: Пожалуйста, укажите ваши USERNAME и PASSWORD в настройках скрипта!")
    else:
        main()
