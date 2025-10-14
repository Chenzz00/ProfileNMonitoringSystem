# WebApp/services.py - PushNotificationService (env-based, no JSON file)
import os
import json
import logging
from datetime import datetime, timedelta

import requests
import google.auth.transport.requests
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

class PushNotificationService:
    """Firebase Cloud Messaging service using env var credentials"""

    PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "ppms-project")

    _cached_token = None
    _token_expiry = None

    @classmethod
    def _load_credentials(cls):
        firebase_key_json = os.environ.get("FIREBASE_KEY_JSON")
        if not firebase_key_json:
            logger.error("FIREBASE_KEY_JSON environment variable not set.")
            return None

        try:
            cred_info = json.loads(firebase_key_json)
            if "private_key" in cred_info:
                cred_info["private_key"] = cred_info["private_key"].replace("\\n", "\n").strip()
            return service_account.Credentials.from_service_account_info(
                cred_info,
                scopes=["https://www.googleapis.com/auth/firebase.messaging"]
            )
        except Exception as e:
            logger.error(f"Failed to load Firebase credentials: {e}")
            return None

    @classmethod
    def get_access_token(cls):
        if cls._cached_token and cls._token_expiry and cls._token_expiry > datetime.utcnow():
            return cls._cached_token

        credentials = cls._load_credentials()
        if not credentials:
            return None

        try:
            request = google.auth.transport.requests.Request()
            credentials.refresh(request)
            cls._cached_token = credentials.token
            cls._token_expiry = credentials.expiry - timedelta(seconds=60)
            logger.info("🔑 New FCM access token generated and cached")
            return cls._cached_token
        except Exception as e:
            logger.error(f"Failed to refresh FCM token: {e}")
            return None

    @classmethod
    def send_push_notification(cls, token: str, title: str, body: str, data: dict = None):
        if not token or not title or not body:
            return {"success": False, "error": "Missing required parameters"}

        access_token = cls.get_access_token()
        if not access_token:
            return {"success": False, "error": "FCM service not configured or credentials invalid"}

        url = f"https://fcm.googleapis.com/v1/projects/{cls.PROJECT_ID}/messages:send"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; UTF-8"}

        payload = {
            "message": {
                "token": token,
                "notification": {"title": title, "body": body},
                "android": {"priority": "high", "notification": {"click_action": "FLUTTER_NOTIFICATION_CLICK","sound": "default","channel_id": "ppms_notifications"}},
                "apns": {"headers": {"apns-priority": "10"}, "payload": {"aps": {"sound": "default","badge": 1}}},
            }
        }

        if data:
            payload["message"]["data"] = {str(k): str(v) for k, v in data.items()}

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            result = response.json()
            if response.status_code == 200:
                return {"success": True, "response": result}
            else:
                return {"success": False, "error": result, "status_code": response.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def is_configured(cls):
        token = cls.get_access_token()
        return (True, "FCM configured successfully") if token else (False, "Failed to generate access token")
