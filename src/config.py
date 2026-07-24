import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
FINNHUB_API_KEY = os.environ["FINNHUB_API_KEY"]
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
# Base URL notifications link back to when tapped (e.g. http://<your-LAN-IP>:8000).
# Must be reachable from your PHONE, not just this machine -- 127.0.0.1 means
# "this device" and won't resolve to anything from another device on the network.
DASHBOARD_BASE_URL = os.environ.get("DASHBOARD_BASE_URL")
ROBINHOOD_USERNAME = os.environ.get("ROBINHOOD_USERNAME")
ROBINHOOD_PASSWORD = os.environ.get("ROBINHOOD_PASSWORD")
