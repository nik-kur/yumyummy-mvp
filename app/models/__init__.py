from app.db.base import Base

# Импорты моделей, чтобы Alembic их видел
from app.models.user import User  # noqa
from app.models.user_day import UserDay  # noqa
from app.models.meal_entry import MealEntry  # noqa
