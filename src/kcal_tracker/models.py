from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("telegram_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="ru")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Europe/Samara")
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    gender: Mapped[str | None] = mapped_column(String(32))
    age: Mapped[int | None] = mapped_column(Integer)
    birth_date: Mapped[date | None] = mapped_column(Date)
    height: Mapped[float | None] = mapped_column(Float)
    weight: Mapped[float | None] = mapped_column(Float)
    activity: Mapped[str | None] = mapped_column(String(64))
    goal: Mapped[str | None] = mapped_column(String(64))
    target_weight_kg: Mapped[float | None] = mapped_column(Float)
    weekly_weight_change_kg: Mapped[float | None] = mapped_column(Float)
    daily_kcal_target: Mapped[int] = mapped_column(Integer, nullable=False, default=2200)
    subscription_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    subscription_plan: Mapped[str] = mapped_column(String(32), nullable=False, default="basic")
    referral_code: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    referred_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    referred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    referral_rewarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_referral_rewarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_active_referral_rewarded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    premium_trial_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    winback_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    weekly_mission_bonus_week: Mapped[date | None] = mapped_column(Date)
    protein_target_g: Mapped[float | None] = mapped_column(Float)
    fat_target_g: Mapped[float | None] = mapped_column(Float)
    carbs_target_g: Mapped[float | None] = mapped_column(Float)
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    meal_reminders_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    weight_reminders_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    breakfast_reminder_time: Mapped[str | None] = mapped_column(String(5), default="10:00")
    lunch_reminder_time: Mapped[str | None] = mapped_column(String(5), default="14:00")
    dinner_reminder_time: Mapped[str | None] = mapped_column(String(5), default="20:30")
    weight_reminder_time: Mapped[str | None] = mapped_column(String(5), default="09:00")
    last_breakfast_reminder_date: Mapped[date | None] = mapped_column(Date)
    last_lunch_reminder_date: Mapped[date | None] = mapped_column(Date)
    last_dinner_reminder_date: Mapped[date | None] = mapped_column(Date)
    last_weight_reminder_date: Mapped[date | None] = mapped_column(Date)
    last_inactivity_reminder_date: Mapped[date | None] = mapped_column(Date)
    apple_health_token: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    entries: Mapped[list[FoodEntry]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    ai_usage: Mapped[list[AIUsage]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    favorite_foods: Mapped[list[FavoriteFood]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    water_logs: Mapped[list[WaterLog]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    weight_logs: Mapped[list[WeightLog]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    activity_logs: Mapped[list[ActivityLog]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    quality_events: Mapped[list[QualityEvent]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    apple_health_syncs: Mapped[list[AppleHealthDailySync]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class FoodEntry(Base):
    __tablename__ = "food_entries"
    __table_args__ = (Index("ix_food_entries_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    food_name: Mapped[str] = mapped_column(String(255), nullable=False)
    kcal: Mapped[float] = mapped_column(Float, nullable=False)
    protein: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    fat: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    carbs: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    weight_g: Mapped[float | None] = mapped_column(Float)
    emoji: Mapped[str | None] = mapped_column(String(16))
    advice: Mapped[str | None] = mapped_column(String(255))
    meal_type: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    photo_thumb_data_url: Mapped[str | None] = mapped_column(Text)
    photo_thumb_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="entries")

    @property
    def name(self) -> str:
        return self.food_name


class ProductCache(Base):
    __tablename__ = "products_cache"

    barcode: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    kcal_100g: Mapped[float | None] = mapped_column(Float)
    protein_100g: Mapped[float | None] = mapped_column(Float)
    fat_100g: Mapped[float | None] = mapped_column(Float)
    carbs_100g: Mapped[float | None] = mapped_column(Float)
    raw_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class FoodCatalogItem(Base):
    __tablename__ = "food_catalog_items"
    __table_args__ = (
        Index("ix_food_catalog_items_normalized", "normalized_name"),
        Index("ix_food_catalog_items_source_trust", "source", "trust_score"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    food_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    kcal: Mapped[float] = mapped_column(Float, nullable=False)
    protein: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    fat: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    carbs: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    weight_g: Mapped[float | None] = mapped_column(Float)
    emoji: Mapped[str | None] = mapped_column(String(16))
    advice: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confirmed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    aliases: Mapped[list[FoodCatalogAlias]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
    )


class FoodCatalogAlias(Base):
    __tablename__ = "food_catalog_aliases"
    __table_args__ = (
        UniqueConstraint("item_id", "normalized_alias"),
        Index("ix_food_catalog_aliases_normalized", "normalized_alias"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("food_catalog_items.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    item: Mapped[FoodCatalogItem] = relationship(back_populates="aliases")


class FavoriteFood(Base):
    __tablename__ = "favorite_foods"
    __table_args__ = (Index("ix_favorite_foods_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    food_name: Mapped[str] = mapped_column(String(255), nullable=False)
    kcal: Mapped[float] = mapped_column(Float, nullable=False)
    protein: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    fat: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    carbs: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    weight_g: Mapped[float | None] = mapped_column(Float)
    emoji: Mapped[str | None] = mapped_column(String(16))
    advice: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="favorite_foods")


class WaterLog(Base):
    __tablename__ = "water_logs"
    __table_args__ = (Index("ix_water_logs_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    amount_ml: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="water_logs")


class WeightLog(Base):
    __tablename__ = "weight_logs"
    __table_args__ = (Index("ix_weight_logs_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="weight_logs")


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    __table_args__ = (Index("ix_activity_logs_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    activity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    kcal: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="activity_logs")


class AppleHealthDailySync(Base):
    __tablename__ = "apple_health_daily_syncs"
    __table_args__ = (
        UniqueConstraint("user_id", "sync_date", "metric"),
        Index("ix_apple_health_sync_user_date", "user_id", "sync_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sync_date: Mapped[date] = mapped_column(Date, nullable=False)
    metric: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="apple_health_syncs")


class AIUsage(Base):
    __tablename__ = "ai_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "usage_date", "request_type"),
        Index("ix_ai_usage_user_date", "user_id", "usage_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    usage_date: Mapped[date] = mapped_column(nullable=False)
    request_type: Mapped[str] = mapped_column(String(32), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="ai_usage")


class AdminSetting(Base):
    __tablename__ = "admin_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_user_created", "user_id", "created_at"),
        Index("ix_payments_status_expires", "status", "expires_at"),
        Index("ux_payments_telegram_charge", "telegram_payment_charge_id", unique=True),
        Index("ux_payments_provider_charge", "provider_payment_charge_id", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    promo_code_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("promo_codes.id", ondelete="SET NULL"),
        index=True,
    )
    amount_stars: Mapped[int | None] = mapped_column(Integer)
    amount_kopecks: Mapped[int | None] = mapped_column(Integer)
    original_amount_stars: Mapped[int | None] = mapped_column(Integer)
    original_amount_kopecks: Mapped[int | None] = mapped_column(Integer)
    promo_code: Mapped[str | None] = mapped_column(String(64))
    promo_discount_percent: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="XTR")
    method: Mapped[str] = mapped_column(String(32), nullable=False, default="stars")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="succeeded")
    payload: Mapped[str] = mapped_column(String(128), nullable=False)
    telegram_payment_charge_id: Mapped[str | None] = mapped_column(String(255))
    provider_payment_charge_id: Mapped[str | None] = mapped_column(String(255))
    yookassa_payment_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    confirmation_url: Mapped[str | None] = mapped_column(String(1024))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="payments")
    promo: Mapped[PromoCode | None] = relationship(back_populates="payments")


class PromoCode(Base):
    __tablename__ = "promo_codes"
    __table_args__ = (
        UniqueConstraint("code"),
        Index("ix_promo_codes_active", "active"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    max_uses: Mapped[int | None] = mapped_column(Integer)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    payments: Mapped[list[Payment]] = relationship(back_populates="promo")


class QualityEvent(Base):
    __tablename__ = "quality_events"
    __table_args__ = (
        Index("ix_quality_events_type_created", "event_type", "created_at"),
        Index("ix_quality_events_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str | None] = mapped_column(String(64))
    query: Mapped[str | None] = mapped_column(String(512))
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped[User | None] = relationship(back_populates="quality_events")
