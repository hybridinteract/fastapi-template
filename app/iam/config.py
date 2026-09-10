from pydantic_settings import BaseSettings, SettingsConfigDict

class AuthConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Provider toggles
    AUTH_EMAIL_PASSWORD_ENABLED: bool = True               # always-on default
    AUTH_GOOGLE_OAUTH_ENABLED:   bool = False
    AUTH_PHONE_OTP_ENABLED:      bool = False

    # Google OAuth (only required when enabled)
    GOOGLE_CLIENT_ID: str = ""

    # Phone OTP (only required when enabled)
    OTP_LENGTH:        int = 6
    OTP_TTL_SECONDS:   int = 300
    OTP_MAX_ATTEMPTS:  int = 5
    OTP_SMS_PROVIDER:  str = "noop"      # "noop" | "twilio" | "msg91" — wired via SmsSender adapter

    # Token policy
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    JWT_REFRESH_TOKEN_EXPIRE_DAYS:   int = 7

    # RBAC
    DEVELOPER_ADMIN_ROLE: str = "developer_admin"

    # User query cache (read-through TTLs; gated globally by settings.CACHE_ENABLED)
    USER_CACHE_TTL_SECONDS:           int = 900   # single-user lookups (15 min)
    USER_ROLE_LIST_CACHE_TTL_SECONDS: int = 900   # active-users-by-role lists

auth_config = AuthConfig()
