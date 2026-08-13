from rest_framework.permissions import BasePermission


class HasAppToken(BasePermission):
    message = "Invalid or missing app token."

    def has_permission(self, request, view) -> bool:
        from django.conf import settings

        expected = getattr(settings, "APP_SHARED_TOKEN", "")
        if not expected:
            return True

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False
        token = auth_header.removeprefix("Bearer ").strip()
        return token == expected
