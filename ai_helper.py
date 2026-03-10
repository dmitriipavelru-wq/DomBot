import json
import httpx
from config import OPENAI_API_KEY
from datetime import datetime

SYSTEM_PROMPT = """Ты помощник семейного планировщика. 
Из текста пользователя извлеки:
- кому назначена задача (поле "who", имя человека или "мне")
- что нужно сделать (поле "task")  
- когда напомнить (поле "when", в формате YYYY-MM-DD HH:MM, используй текущее время как ориентир)

Отвечай ТОЛЬКО валидным JSON без markdown. Пример:
{"who": "бабушке", "task": "принять лекарство", "when": "2024-01-15 09:00"}

Если время не указано — поставь через 1 час от текущего.
Если кто не указан — "мне".
"""

async def parse_task_with_ai(text: str) -> dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Текущее время: {now}\nЗапрос: {text}"}
                    ],
                    "max_tokens": 200,
                    "temperature": 0
                }
            )
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        return None
