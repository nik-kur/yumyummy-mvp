from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Онбординг данные
    goal_type = Column(String, nullable=True)  # 'lose', 'maintain', 'gain'
    gender = Column(String, nullable=True)  # 'male', 'female'
    age = Column(Integer, nullable=True)
    height_cm = Column(Integer, nullable=True)
    weight_kg = Column(Float, nullable=True)
    activity_level = Column(String, nullable=True)  # 'sedentary', 'light', 'moderate', 'high', 'very_high'

    # Целевые КБЖУ
    target_calories = Column(Float, nullable=True)
    target_protein_g = Column(Float, nullable=True)
    target_fat_g = Column(Float, nullable=True)
    target_carbs_g = Column(Float, nullable=True)

    # Часовой пояс пользователя
    timezone = Column(String, nullable=True)  # e.g. 'Europe/Moscow', 'America/New_York'

    # Статус онбординга
    onboarding_completed = Column(Boolean, default=False, nullable=False)

    # Billing / Subscription
    trial_started_at = Column(DateTime(timezone=True), nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    subscription_plan_id = Column(String, nullable=True)
    subscription_started_at = Column(DateTime(timezone=True), nullable=True)
    subscription_ends_at = Column(DateTime(timezone=True), nullable=True)
    subscription_auto_renew = Column(Boolean, default=True, nullable=True)
    subscription_telegram_charge_id = Column(String, nullable=True)
    subscription_provider = Column(String, nullable=True)
    subscription_gumroad_id = Column(String, nullable=True)
    subscription_paddle_id = Column(String, nullable=True)
    usage_cost_current_period = Column(Float, default=0.0, nullable=False)
    usage_period_start = Column(DateTime(timezone=True), nullable=True)

    # Lifecycle notifications
    first_meal_after_onboarding_at = Column(DateTime(timezone=True), nullable=True)
    features_used = Column(String, nullable=True)  # JSON: {"voice": false, "barcode": false, "my_menu": false, "what_to_eat": false}
    meals_count_trial = Column(Integer, default=0, nullable=False)

    # Связи
    days = relationship("UserDay", back_populates="user")
    meals = relationship("MealEntry", back_populates="user")
    saved_meals = relationship("SavedMeal", back_populates="user")
    payment_events = relationship("PaymentEvent", back_populates="user")
    usage_records = relationship("UsageRecord", back_populates="user")
