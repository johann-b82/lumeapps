"""Signage ORM models — v1.16 Digital Signage.

Eight tables for the signage CMS: media library, playlists, playlist items,
devices, device tags, two tag-map join tables, and pairing sessions.

All tables carry TIMESTAMPTZ NOT NULL `created_at` / `updated_at` columns
(decision D-12). FKs follow decision D-16: CASCADE where owning parent
controls lifetime; RESTRICT on `playlist_items.media_id` so deleting a media
row that is referenced by a playlist fails loudly instead of silently losing
playlist content. `SignagePairingSession` has a partial-unique index on
`code` scoped to rows still active (not expired, not claimed) per D-15.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class SignageMedia(Base):
    """Media library row: images, videos, PDFs, PPTX, URLs, HTML snippets."""

    __tablename__ = "signage_media"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('image','video','pdf','pptx','url','html')",
            name="ck_signage_media_kind",
        ),
        CheckConstraint(
            "conversion_status IS NULL OR conversion_status IN ('pending','processing','done','failed')",
            name="ck_signage_media_conversion_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(127), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    conversion_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    slide_paths: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    conversion_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    conversion_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    html_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    playlist_items: Mapped[list["SignagePlaylistItem"]] = relationship(
        "SignagePlaylistItem", back_populates="media"
    )


class SignagePlaylist(Base):
    """Ordered collection of media items, targeting devices via tag maps."""

    __tablename__ = "signage_playlists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    items: Mapped[list["SignagePlaylistItem"]] = relationship(
        "SignagePlaylistItem",
        back_populates="playlist",
        cascade="all, delete-orphan",
        order_by="SignagePlaylistItem.position",
    )


class SignagePlaylistItem(Base):
    """One entry in a playlist; references a media row with RESTRICT on delete."""

    __tablename__ = "signage_playlist_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    playlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("signage_playlists.id", ondelete="CASCADE"),
        nullable=False,
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("signage_media.id", ondelete="RESTRICT"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_s: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("10")
    )
    transition: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    playlist: Mapped["SignagePlaylist"] = relationship(
        "SignagePlaylist", back_populates="items"
    )
    media: Mapped["SignageMedia"] = relationship(
        "SignageMedia", back_populates="playlist_items"
    )


class SignageDevice(Base):
    """Registered signage player device (Raspberry Pi kiosk)."""

    __tablename__ = "signage_devices"
    __table_args__ = (
        CheckConstraint(
            "status IN ('online','offline','pending')",
            name="ck_signage_devices_status",
        ),
        # Phase 62-01 CAL-BE-01 / D-01: rotation restricted to the four
        # labwc-supported wayland transforms.
        CheckConstraint(
            "rotation IN (0, 90, 180, 270)",
            name="ck_signage_devices_rotation",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # Phase 42 populates; Text accommodates both opaque-sha256 and JWT formats.
    device_token_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # No FK — item may be deleted while device still cached it locally.
    current_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'offline'")
    )
    # Phase 43 D-11: last-known playlist ETag written by heartbeat endpoint.
    current_playlist_etag: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Phase 62-01 CAL-BE-01 — calibration columns.
    # D-01: rotation is one of 0/90/180/270 (labwc transforms). D-07 backfills
    # existing rows with rotation=0 via server_default.
    rotation: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    # D-02: NULL means "use current HDMI mode" — sidecar makes no wlr-randr
    # --mode call when hdmi_mode IS NULL.
    hdmi_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # D-03: single device-level audio on/off toggle.
    audio_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SignageDeviceTag(Base):
    """Tag label for tag-based playlist routing (e.g., lobby, production)."""

    __tablename__ = "signage_device_tags"
    __table_args__ = (
        Index("uq_signage_device_tags_name", "name", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SignageDeviceTagMap(Base):
    """Join table: which tags apply to which devices (composite PK)."""

    __tablename__ = "signage_device_tag_map"

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("signage_devices.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("signage_device_tags.id", ondelete="CASCADE"),
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SignagePlaylistTagMap(Base):
    """Join table: which tags a playlist targets (composite PK)."""

    __tablename__ = "signage_playlist_tag_map"

    playlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("signage_playlists.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("signage_device_tags.id", ondelete="CASCADE"),
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SignagePairingSession(Base):
    """6-digit pairing code a fresh Pi displays until an admin claims it.

    Partial-unique index on `code` scoped to rows where `claimed_at IS NULL` —
    guarantees only one unclaimed pairing session per code at a time (D-15).

    SGN-DB-02 amendment (2026-04-18): the original plan included
    `expires_at > now()` in the predicate, but PostgreSQL rejects non-IMMUTABLE
    functions (like `now()`, which is STABLE) in partial-index predicates
    (errcode 42P17). Expiration is instead enforced by the Phase 42 03:00 UTC
    cron cleanup, which transitions expired rows out of the unclaimed state.
    """

    __tablename__ = "signage_pairing_sessions"
    __table_args__ = (
        Index(
            "uix_signage_pairing_sessions_code_active",
            "code",
            unique=True,
            postgresql_where=text("claimed_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("signage_devices.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SignageSchedule(Base):
    """Time-based playlist schedule — v1.18 Phase 51 SGN-TIME-01.

    A schedule binds a playlist to a (weekday, time-window) gate. The resolver
    picks the highest (priority DESC, updated_at DESC) enabled schedule whose
    weekday_mask matches now.weekday() and start_hhmm <= now_hhmm < end_hhmm,
    and whose playlist's tags overlap the device's tags. No midnight-spanning
    windows (D-07) — operators split "22:00-02:00" into two rows.

    Bit ordering (D-05): bit 0 = Monday .. bit 6 = Sunday.
    Time format: packed integer HHMM (e.g., 730 = 07:30, 1430 = 14:30).
    """

    __tablename__ = "signage_schedules"
    __table_args__ = (
        CheckConstraint(
            "weekday_mask BETWEEN 0 AND 127",
            name="ck_signage_schedules_weekday_mask",
        ),
        CheckConstraint(
            "start_hhmm >= 0 AND start_hhmm <= 2359",
            name="ck_signage_schedules_start_hhmm",
        ),
        CheckConstraint(
            "end_hhmm >= 0 AND end_hhmm <= 2359",
            name="ck_signage_schedules_end_hhmm",
        ),
        CheckConstraint(
            "start_hhmm < end_hhmm",
            name="ck_signage_schedules_no_midnight_span",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    playlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("signage_playlists.id", ondelete="RESTRICT"),
        nullable=False,
    )
    weekday_mask: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_hhmm: Mapped[int] = mapped_column(Integer, nullable=False)
    end_hhmm: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SignageHeartbeatEvent(Base):
    """Phase 53 SGN-ANA-01 — per-heartbeat append-only log.

    One row per successful POST /api/signage/player/heartbeat. Retention 25 h,
    pruned by the existing heartbeat sweeper in app/scheduler.py.

    Composite PK (device_id, ts) — no surrogate id (see 53-RESEARCH Pattern 2):
      - Insert rate ~1/min/device → natural uniqueness is free.
      - Prune (WHERE ts < cutoff) → PK-ordered scan, no secondary lookup.
      - Analytics (WHERE ts >= cutoff GROUP BY device_id) → PK covers filter+group.

    Idempotency on heartbeat insert is achieved at call-site via
    `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_nothing(
        index_elements=["device_id", "ts"])`.
    """

    __tablename__ = "signage_heartbeat_event"

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("signage_devices.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        server_default=func.now(),
    )
