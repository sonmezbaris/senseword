"""ORM models package.

Importing the models here ensures SQLAlchemy registers them on the metadata
when ``app.models`` is imported (used by ``database.init_db``).
"""

from app.models.catalog import CatalogWord, UserWordAnswer
from app.models.learning_path import (
    LearningPath,
    LearningPathProgress,
    LearningPathWord,
)
from app.models.mission import DailyMissionProgress
from app.models.review import ReviewLog
from app.models.user import User
from app.models.usage import UserDailyUsage
from app.models.vocabulary import Vocabulary
from app.models.word_progress import UserWordProgress

__all__ = [
    "User",
    "Vocabulary",
    "ReviewLog",
    "CatalogWord",
    "UserWordAnswer",
    "LearningPath",
    "LearningPathWord",
    "LearningPathProgress",
    "UserWordProgress",
    "DailyMissionProgress",
    "UserDailyUsage",
]
