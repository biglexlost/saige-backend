# /src/utils.py

import os
import requests
import logging
from config import config

# Set up basic logging to see success or failure messages in your Render logs
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Get the URL from the single source of truth
DISCORD_WEBHOOK_URL = config.discord_webhook_url


def send_discord_alert(content: str = None, embed: dict = None):
    """
    Sends a message or a rich embed to the Discord webhook.
    """
    # 1. Check if the webhook URL is configured
    if not DISCORD_WEBHOOK_URL or "placeholder" in DISCORD_WEBHOOK_URL:
        logging.error("Discord webhook URL is not set or is a placeholder.")
        return

    # 2. Prepare the payload for Discord's API
    payload = {}
    if content:
        payload["content"] = content
    if embed:
        # Discord's API expects the 'embeds' key to be a list of embed objects
        payload["embeds"] = [embed]

    # Don't send an empty payload
    if not payload:
        logging.warning("send_discord_alert was called with no content or embed.")
        return

    # 3. Send the request with error handling
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        # Raise an exception if the request returned an unsuccessful status code (like 404 or 500)
        response.raise_for_status()
        logging.info("Discord alert sent successfully.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send Discord alert: {e}")
