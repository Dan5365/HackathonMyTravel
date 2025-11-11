import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()
genai.configure(api_key="AIzaSyDT7vLvYPpM_qJ6U3fEskxmIMKizl3uwDk")

model = genai.GenerativeModel("gemini-2.5-flash-lite")

prompt = "Напиши описание туристического места 'Шымбулак' в Казахстане, 150 слов, красиво и неформально."
response = model.generate_content(prompt)

print(response.text)
