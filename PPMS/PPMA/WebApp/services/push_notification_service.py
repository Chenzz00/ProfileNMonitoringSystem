# WebApp/services.py - Optimized version with token caching
import requests
import google.auth.transport.requests
from google.oauth2 import service_account
from django.conf import settings
import logging
import json
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class PushNotificationService:
    """Firebase Cloud Messaging service for sending push notifications"""
    
    SERVICE_ACCOUNT_FILE = getattr(settings, 'FIREBASE_KEY_PATH', None)
    PROJECT_ID = "push-notification-3afa0"  # Replace with your actual Firebase Project ID

    # Cached token and expiry
    _cached_token = None
    _token_expiry = None

    @classmethod
    def get_access_token(cls):
        """Generate or reuse OAuth2 token using service account"""
        try:
            if cls._cached_token and cls._token_expiry and cls._token_expiry > datetime.utcnow():
                return cls._cached_token

            if not cls.SERVICE_ACCOUNT_FILE:
                logger.warning("FIREBASE_KEY_PATH not configured in settings")
                return None
            
            if not os.path.exists(cls.SERVICE_ACCOUNT_FILE):
                logger.error(f"Firebase service account file not found: {cls.SERVICE_ACCOUNT_FILE}")
                return None
            
            SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]
            credentials = service_account.Credentials.from_service_account_file(
                str(cls.SERVICE_ACCOUNT_FILE), scopes=SCOPES
            )
            request = google.auth.transport.requests.Request()
            credentials.refresh(request)

            # Cache token + expiry
            cls._cached_token = credentials.token
            cls._token_expiry = credentials.expiry
            logger.info("🔑 New FCM access token generated and cached")

            return cls._cached_token
        except Exception as e:
            logger.error(f"Failed to get FCM access token: {e}")
            return None

    @classmethod
    def send_push_notification(cls, token, title, body, data=None):
        """Send push notification via FCM HTTP v1 API"""
        try:
            if not token or not title or not body:
                return {"success": False, "error": "Missing required parameters: token, title, or body"}
            
            # Check if service is configured
            access_token = cls.get_access_token()
            if not access_token:
                return {"success": False, "error": "FCM service not configured or credentials invalid"}
            
            url = f"https://fcm.googleapis.com/v1/projects/{cls.PROJECT_ID}/messages:send"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; UTF-8",
            }
            
            # CORRECTED PAYLOAD STRUCTURE
            payload = {
                "message": {
                    "token": token,
                    "notification": {
                        "title": title,
                        "body": body,
                    },
                    "android": {
                        "priority": "high",
                        "notification": {
                            "click_action": "FLUTTER_NOTIFICATION_CLICK",
                            "sound": "default",
                            "channel_id": "ppms_notifications"
                        }
                    },
                    "apns": {
                        "headers": {
                            "apns-priority": "10"
                        },
                        "payload": {
                            "aps": {
                                "sound": "default",
                                "badge": 1
                            }
                        }
                    }
                }
            }
            
            # Convert data values to strings (FCM requirement)
            if data:
                payload["message"]["data"] = {k: str(v) for k, v in data.items()}

            logger.info(f"Sending FCM notification to token: {token[:20]}...")
            logger.debug(f"Notification payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            result = response.json()
            
            if response.status_code == 200:
                logger.info(f"FCM notification sent successfully: {result}")
                return {"success": True, "response": result}
            else:
                logger.error(f"FCM notification failed: {response.status_code} - {result}")
                return {"success": False, "error": result, "status_code": response.status_code}
                
        except Exception as e:
            logger.error(f"Exception sending FCM notification: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def is_configured(cls):
        """Check if the FCM service is properly configured"""
        try:
            if not cls.SERVICE_ACCOUNT_FILE:
                return False, "FIREBASE_KEY_PATH not set in settings"
            
            if not os.path.exists(cls.SERVICE_ACCOUNT_FILE):
                return False, f"Service account file not found: {cls.SERVICE_ACCOUNT_FILE}"
            
            # Try to get access token
            token = cls.get_access_token()
            if token:
                return True, "FCM configured successfully"
            else:
                return False, "Failed to generate access token"
            
        except Exception as e:
            return False, f"FCM configuration error: {str(e)}"
