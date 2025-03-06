import os

import requests

from app.models.antifraud import AntifraudRequest


async def call_antifraud(request: AntifraudRequest):
    antifraud_address = os.getenv('ANTIFRAUD_ADDRESS', "localhost:9090")
    antifraud_url = f"http://{antifraud_address}/api/validate"
    data = {
        "user_email": request.get("user_email"),
        "promo_id": request.get("promo_id"),
    }
    headers = {
        'Content-Type': 'application/json'
    }

    for _ in range(2):
        response = requests.post(url=antifraud_url, json=data, headers=headers)
        if response.status_code == 200:
            return response.json()
    return None