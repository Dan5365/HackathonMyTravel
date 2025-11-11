# Mycar - MyTravel Automation Project
# Заголовок

Тысячи зон отдыха, курортов, глэмпингов, санаториев и турбаз в Казахстане до сих пор не представлены онлайн.  
Они теряют клиентов, а туристы — возможности.

**Цель MyTravel** — оцифровать эти объекты, собрать единый каталог и подключать их к платформе через автоматизацию:  
парсинг + ИИ-анализ + рассылка WhatsApp.


## Что оно делает?

Проект состоит из 4 основных модулей:

### ✅ 1. Google Maps Scraper (`scarper.py`)
Собирает данные по поисковым запросам:
- Название
- Адрес
- Рейтинг
- Телефон
- Координаты
- Ссылки и отзывы
- Сохранение в CSV / XLSX

### ✅ 2. 2ГИС Scraper (dgis_scraper.py)

Собирает данные о местах через API 2ГИС:
- Название объекта
- Адрес
- Телефон
- Категория
- Координаты
- Ссылки на сайт/страницу
- Сохранение в CSV / XLSX

### ✅ 3. Instagram Parser (`inst_parser_hack3.py`)
Работает по списку аккаунтов:
- Количество подписчиков
- Активность
- Описание
- Ссылки
- Фото (по желанию)
- Выгрузка в CSV и JSON

### ✅ 4. WhatsApp Outreach Bot (`whatsapp_send.py`)
Автоматически:
- Определяет тип объекта через OpenAI (глэмпинг / база отдыха / отель и т.д.)
- Генерирует персонализированное сообщение
- Отправляет его через WhatsApp Business API / pywhatkit
- Форматирует номера телефонов
- Логирует отправки

---

## Tech Stack

**Языки и библиотеки:**
- Python 3.x
- Playwright / Selenium (если нужно)
- Pandas
- PyWhatKit
- Requests
- OpenAI API
- dotenv

**Интеграции:**
- Google Maps
- Instagram public data
- WhatsApp Web (Desktop automation)
- CSV/JSON/XLSX экспорт


**Этап Запуска:**
1. Клонируем репозиторий
```
git clone https://github.com/Dan5365/Hackathon-.git
cd https://github.com/Dan5365/Hackathon-.git
```
2. Установка зависимостей

Создате виртуальное окружение и установи зависимости:
```
pip install -r requirements.txt
```
или
```
pip install fastapi uvicorn pandas requests
```

3.Запуск проекта
3.1 Для 2gis
```
uvicorn main:app --reload
```

3.2 Для google maps
```
python scripts/scarper.py -s "Астана Зона отдыха" -t 50 --timeout 120 --headless False
```

3.3 Для инстаграм
```
python scripts/inst_parser_hack4.py
```

После запуска приложение будет доступно по адресу:
 http://127.0.0.1:8000

 **Структура проекта**

 main.py                 # основной файл приложения
routers/                # маршруты API
utils/                  # вспомогательные функции
scripts/                # скрипты и парсеры
data/                   # данные (raw, processed, meta)
output/                 # результаты анализа


# Скриншоты
<img width="982" height="568" alt="{5BD2F2B5-81AB-405D-8D6F-ED9F3B9325D4}" src="https://github.com/user-attachments/assets/788b8167-ecf8-4b71-9abd-00805808c5c8" />
<img width="1019" height="581" alt="{433FB2AB-1410-40B1-AE45-B1373101A193}" src="https://github.com/user-attachments/assets/ba369523-f381-4df9-aa43-5ea5a94c903f" />
<img width="1009" height="575" alt="{B9677F79-F16C-48EF-B148-B88F1C49EDE4}" src="https://github.com/user-attachments/assets/6f512d20-1d39-4b03-94f6-b305358ada53" />
<img width="997" height="565" alt="{0251568C-9EB5-42B9-B74D-BA62E885FC50}" src="https://github.com/user-attachments/assets/066d851e-b6ee-4ef3-842d-3bceb39d6eb0" />
<img width="1004" height="573" alt="{0AFF23CF-3368-48B0-B838-C4C802F6497A}" src="https://github.com/user-attachments/assets/e78eb1f8-fc59-4dc9-a800-2b2f3897ac64" />


© 2025 Daniyal. All rights reserved.
Проект разрешён только для личного и учебного использования.
Коммерческое использование без разрешения владельца репозитория запрещено.


