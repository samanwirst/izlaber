from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class InternalServiceUser:
    is_authenticated = True
    is_anonymous = False

    def __str__(self) -> str:
        return "internal-service"


class InternalAPIKeyAuthentication(BaseAuthentication):
    header_name = "HTTP_X_INTERNAL_API_KEY"
    allowed_settings: tuple[str, ...] = ()

    def authenticate(self, request):
        provided_key = request.META.get(self.header_name)
        if not provided_key:
            raise AuthenticationFailed("Missing internal API key.")

        allowed_keys = [
            getattr(settings, setting_name, "")
            for setting_name in self.allowed_settings
        ]
        if provided_key not in {key for key in allowed_keys if key}:
            raise AuthenticationFailed("Invalid internal API key.")

        return InternalServiceUser(), None


class BotAPIKeyAuthentication(InternalAPIKeyAuthentication):
    allowed_settings = ("BOT_API_KEY",)


class ParserAPIKeyAuthentication(InternalAPIKeyAuthentication):
    allowed_settings = ("PARSER_API_KEY",)
