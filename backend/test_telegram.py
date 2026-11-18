
import json
import urllib.parse
import urllib.request
from pathlib import Path

env_path = Path(".env")

if not env_path.exists():
    raise FileNotFoundError("Cannot find backend/.env")

env = {}

for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()

    if not line or line.startswith("#") or "=" not in line:
        continue

    key, value = line.split("=", 1)
    env[key.strip()] = value.strip().strip('"').strip("'")

token = env.get("TELEGRAM_BOT_TOKEN")
chat_id = env.get("TELEGRAM_CHAT_ID")

if not token or not chat_id:
    raise ValueError("Missing Telegram token or Chat ID in .env")

url = f"https://api.telegram.org/bot{token}/sendMessage"

data = urllib.parse.urlencode({
    "chat_id": chat_id,
    "text": "🌊 Welcome to FloodPulse AI!\n\nYour Telegram connection is working successfully."
}).encode("utf-8")

request = urllib.request.Request(url, data=data)

with urllib.request.urlopen(request, timeout=20) as response:
    result = json.loads(response.read().decode())

if result.get("ok"):
    print("SUCCESS: Telegram message sent!")
else:
    print("FAILED:", result)
