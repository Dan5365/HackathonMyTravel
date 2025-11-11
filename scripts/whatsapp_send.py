import pandas as pd
from openai import OpenAI
import openai
import pywhatkit
import time
import requests
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai.api_key)

class WhatsAppCampaign:
    def __init__(self, csv_file):
        self.csv_file = csv_file
        self.df = None

    def load_data(self):
        try:
            self.df = pd.read_csv(self.csv_file)
            return True
        except Exception as e:
            print(f"Ошибка CSV: {e}")
            return False

    def analyze_location(self, name, address):
        """Анализирует тип объекта по названию"""
        prompt = f"""
        Проанализируй это место по названию и адресу и определи тип объекта:
        Название: {name}
        Адрес: {address}

        Верни ТОЛЬКО одно слово - тип объекта. Варианты:
        - глэмпинг
        - отель
        - зона отдыха 
        - парк
        - кафе
        - ресторан
        - турбаза
        - кемпинг
        - санаторий
        - дом отдыха
        - спортивный комплекс
        - развлекательный центр
        - гостиница
        - мотель
        - хостел
        - база отдыха
        - другое

        Только одно слово в ответе!
        """

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            location_type = response.choices[0].message.content.strip().lower()
            return location_type
        except Exception as e:
            print(f"Ошибка анализа локации: {e}")
            return "место"

    def generate_message(self, name, location_type, address):
        """Генерирует персонализированное сообщение через OpenAI"""

        # Словарь для красивого описания типов
        type_descriptions = {
            "глэмпинг": "потрясающий глэмпинг",
            "отель": "прекрасный отель",
            "зона отдыха": "уютную зону отдыха",
            "парк": "красивый парк",
            "кафе": "уютное кафе",
            "ресторан": "прекрасный ресторан",
            "турбаза": "отличную турбазу",
            "кемпинг": "комфортный кемпинг",
            "санаторий": "замечательный санаторий",
            "дом отдыха": "уютный дом отдыха",
            "спортивный комплекс": "современный спортивный комплекс",
            "развлекательный центр": "популярный развлекательный центр",
            "гостиница": "комфортную гостиницу",
            "мотель": "удобный мотель",
            "хостел": "стильный хостел",
            "база отдыха": "прекрасную базу отдыха",
            "место": "ваше прекрасное место",
            "другое": "ваш замечательный объект"
        }

        description = type_descriptions.get(location_type, "ваше прекрасное место")

        prompt = f"""
        Создай персонализированное сообщение для WhatsApp бизнесу. Тон: дружелюбный, профессиональный.

        Данные:
        - Название: {name}
        - Тип: {description}
        - Адрес: {address}

        Шаблон для примера:
        Привет, [Название]!
        Мы заметили ваш [тип объекта] рядом с [адрес]. Ваше место явно заслуживает большей аудитории туристов!

        mytravel.kz — это топовая платформа путешествий в Казахстане, где вы получите:
        • 10K+ активных туристов ежемесячно
        • Лучший рейтинг для премиум объектов  
        • Инструменты управления бронированиями

        Хотим добавить вас в каталог. Можно поговорить?

        Спасибо,
        Команда mytravel.kz

        Сделай сообщение естественным и персонализированным под {description}. 
        Используй настоящее название "{name}" и адрес "{address} но postal code не нужен здесь, пример 010000 чтобы его не было, не добавляй".
        Максимум 7-10 строк.
        """

        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            message = response.choices[0].message.content.strip()
            return message
        except Exception as e:
            print(f"Ошибка генерации сообщения: {e}")
            # Fallback сообщение
            return f"""Привет, {name}!
Мы заметили ваш {description} рядом с {address}. Ваше место заслуживает большей аудитории туристов!

mytravel.kz — топовая платформа путешествий в Казахстане с 10K+ туристов ежемесячно.

Хотим добавить вас в каталог. Можно поговорить?

Команда mytravel.kz"""

    def send_whatsapp_message(self, phone_number, message):
        """Отправляет сообщение через WhatsApp"""
        try:
            # Форматируем номер
            phone = self.format_phone_number(phone_number)
            if not phone:
                print(f"Неверный номер: {phone_number}")
                return False

            # Получаем текущее время + 2 минуты для отправки
            now = datetime.now()
            hour = now.hour
            minute = (now.minute + 2) % 60

            print(f"📱 Отправка на {phone} в {hour}:{minute:02d}")

            # Отправляем сообщение
            pywhatkit.sendwhatmsg(phone, message, hour, minute, 15, True, 2)

            print(f"Сообщение отправлено на {phone}")
            return True

        except Exception as e:
            print(f"Ошибка отправки на {phone_number}: {e}")
            return False

    def format_phone_number(self, phone):
        """Форматирует номер телефона"""
        if pd.isna(phone):
            return None

        phone_str = str(phone).strip()
        cleaned = ''.join(filter(str.isdigit, phone_str))

        if cleaned.startswith('8') and len(cleaned) == 11:
            return '+7' + cleaned[1:]
        elif cleaned.startswith('7') and len(cleaned) == 11:
            return '+' + cleaned
        elif len(cleaned) == 10:
            return '+7' + cleaned
        elif cleaned.startswith('870') and len(cleaned) == 11:
            return '+7' + cleaned[2:]
        else:
            print(f"Странный номер: {cleaned}")
            return '+' + cleaned

    def run_campaign(self, delay_minutes=5):
        if not self.load_data():
            return

        results = []

        for index, row in self.df.iterrows():
            try:
                print(f"\n Обрабатываю {index + 1}/{len(self.df)}: {row['name']}")

                # Проверяем обязательные поля
                if pd.isna(row.get('phone_number')):
                    print("нет номера телефона")
                    continue

                if pd.isna(row.get('name')):
                    print("нет названия")
                    continue

                # Анализируем тип объекта
                location_type = self.analyze_location(
                    row['name'],
                    row.get('address', '')
                )
                print(f"Тип объекта: {location_type}")

                # Генерируем сообщение
                message = self.generate_message(
                    name=row['name'],
                    location_type=location_type,
                    address=row.get('address', 'неизвестно')
                )

                print(f"💬 Сгенерировано сообщение:")
                print("-" * 40)
                print(message)
                print("-" * 40)

                # Отправляем в WhatsApp
                success = self.send_whatsapp_message(row['phone_number'], message)

                results.append({
                    'name': row['name'],
                    'phone': row['phone_number'],
                    'type': location_type,
                    'success': success,
                    'message_preview': message[:100] + '...'
                })

                if index < len(self.df) - 1:
                    delay_seconds = delay_minutes * 60
                    print(f"{delay_minutes} минут перед следующим сообщением...")
                    time.sleep(delay_seconds)

            except Exception as e:
                print(f"Ошибка обработки {row['name']}: {e}")
                results.append({
                    'name': row['name'],
                    'phone': row.get('phone_number', 'N/A'),
                    'success': False,
                    'error': str(e)
                })

        # Выводим результаты
        print(f"\nRESULTS:")
        print("=" * 50)
        successful = sum(1 for r in results if r['success'])
        print(f"Успешно отправлено: {successful}/{len(results)}")

        for result in results:
            status = "Yes" if result['success'] else "No"
            print(f"{status} {result['name']} - {result.get('type', 'N/A')}")

        return results


#ЗАПУСК ПРОГРАММЫ
if __name__ == "__main__":
    CSV_FILE = "google_maps_Астана_Зона_отдыха_20251019_082206.csv"

    # Создаем кампанию
    campaign = WhatsAppCampaign(CSV_FILE)

    print("ЗАПУСК WHATSAPP КАМПАНИИ")
    print("=" * 30)

    #5 min
    results = campaign.run_campaign(delay_minutes=5)

    print(f"\nDone")
