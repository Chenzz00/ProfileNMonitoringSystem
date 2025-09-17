# WebApp/services/__init__.py
try:
    from .push_notification_service import PushNotificationService
    print("Successfully imported PushNotificationService")
except ImportError as e:
    print(f"Failed to import PushNotificationService: {e}")
    # Create a dummy class to prevent import errors
    class PushNotificationService:
        @classmethod
        def send_push_notification(cls, token, title, body, data=None):
            return {"success": False, "error": "Service not available"}

__all__ = ['PushNotificationService']