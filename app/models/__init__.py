from app.db.base import Base

# Импорты моделей, чтобы Alembic их видел
from app.models.user import User  # noqa
from app.models.user_day import UserDay  # noqa
from app.models.meal_entry import MealEntry  # noqa
from app.models.saved_meal import SavedMeal  # noqa
from app.models.saved_meal_item import SavedMealItem  # noqa
from app.models.payment_event import PaymentEvent  # noqa
from app.models.usage_record import UsageRecord  # noqa
from app.models.churn_survey import ChurnSurvey  # noqa
from app.models.notification_event import NotificationEvent  # noqa
