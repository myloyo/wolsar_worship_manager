from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from worship_bot.infrastructure.models.base import Base, utc_now


class SongRecord(Base):
    __tablename__ = "songs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    song_name: Mapped[str] = mapped_column(String(200))
    song_lyric: Mapped[str | None] = mapped_column(Text, nullable=True)
    youtube_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vocals_line: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class EventSongRecord(Base):
    __tablename__ = "event_songs"
    __table_args__ = (UniqueConstraint("event_id", "song_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id", ondelete="CASCADE"))
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EventSongSetVersionRecord(Base):
    __tablename__ = "event_song_set_versions"
    __table_args__ = (UniqueConstraint("event_id", "version_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    version_number: Mapped[int] = mapped_column(Integer)
    edited_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EventSongSetVersionItemRecord(Base):
    __tablename__ = "event_song_set_version_items"
    __table_args__ = (
        UniqueConstraint("version_id", "position"),
        UniqueConstraint("version_id", "song_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("event_song_set_versions.id", ondelete="CASCADE")
    )
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id", ondelete="RESTRICT"))
    position: Mapped[int] = mapped_column(Integer)


class SongKeyVersionRecord(Base):
    __tablename__ = "songs_key_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id", ondelete="CASCADE"))
    song_key_version: Mapped[str] = mapped_column(String(16))
    audio_file_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
