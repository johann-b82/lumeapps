from uuid import UUID

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DIRECTUS_SECRET: str = Field(..., description="Directus JWT signing secret (HS256)")
    DIRECTUS_ADMINISTRATOR_ROLE_UUID: UUID
    DIRECTUS_VIEWER_ROLE_UUID: UUID
    # QS role UUID — optional so environments without a provisioned QS role
    # still boot. Only mapped to Role.QS when set (see directus_auth._role_map).
    DIRECTUS_QS_ROLE_UUID: UUID | None = None

    # Phase 44 D-11: Directus is the binary store for raw PPTX uploads.
    # The backend streams multipart bodies into Directus /files using its
    # admin token; the returned file UUID is persisted as `signage_media.uri`.
    DIRECTUS_URL: str = Field(
        default="http://directus:8055",
        description="Base URL of the Directus service inside the compose network",
    )
    DIRECTUS_ADMIN_TOKEN: str = Field(
        default="",
        description="Static Directus admin token used by the backend for file uploads",
    )

    # D-04: HS256 signing key for device JWT — separate trust domain from Directus.
    # No default — app fails fast if unset.
    SIGNAGE_DEVICE_JWT_SECRET: str = Field(
        ..., description="HS256 signing key for signage device JWTs (scope=device)"
    )


settings = Settings()
