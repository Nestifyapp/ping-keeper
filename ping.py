import requests
import time
from datetime import datetime

# Add your endpoints here
ENDPOINTS = [
    "https://your-backend-1.onrender.com/health",
    "https://your-backend-2.onrender.com/",
    "https://your-app.vercel.app/",
]

TIMEOUT_SECONDS = 10


def ping(url):
    try:
        response = requests.get(url, timeout=TIMEOUT_SECONDS)
        print(
            f"[{datetime.utcnow()}] {url} -> {response.status_code}"
        )
    except Exception as e:
        print(
            f"[{datetime.utcnow()}] {url} -> ERROR: {str(e)}"
        )


def main():
    for url in ENDPOINTS:
        ping(url)


if __name__ == "__main__":
    main()
