
import json
import urllib.parse
import urllib.request
from pathlib import Path

# Read credentials from backend/.env
env = {}

for line in Path(".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()

    if not line or line.startswith("#") or "=" not in line:
        continue

    key, value = line.split("=", 1)
    env[key.strip()] = value.strip().strip('"').strip("'")

token = env.get("TELEGRAM_BOT_TOKEN")
chat_id = env.get("TELEGRAM_CHAT_ID")

if not token or not chat_id:
    raise ValueError("Telegram token or Chat ID is missing in .env")

# Prepare Telegram message
url = f"https://api.telegram.org/bot{token}/sendMessage"

data = urllib.parse.urlencode({
    "chat_id": chat_id,
    "text": (
        "🌊 Welcome to FloodPulse AI!\n\n"
        "Your Telegram connection is working successfully.\n"
        "Cambodia Flood Monitoring System."
    )
}).encode()

request = urllib.request.Request(url, data=data)

# Send message
with urllib.request.urlopen(request, timeout=20) as response:
    result = json.loads(response.read().decode())

if result.get("ok"):
    print("SUCCESS: Telegram message sent!")
else:
    print("FAILED:", result)
