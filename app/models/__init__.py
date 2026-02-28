from app.db.base import Base

# Импорты моделей, чтобы Alembic их видел
from app.models.user import User  # noqa
from app.models.user_day import UserDay  # noqa
from app.models.meal_entry import MealEntry  # noqa
from app.models.saved_meal import SavedMeal  # noqa
from app.models.saved_meal_item import SavedMealItem  # noqa
