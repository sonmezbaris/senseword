"""Learning path service.

Read/query learning paths and their ordered words, plus a small idempotent
seeding helper. Built entirely on top of the existing ``CatalogWord`` data, so
the word catalog and personal-word features remain untouched.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.catalog import CatalogWord, UserWordAnswer
from app.models.learning_path import (
    LearningPath,
    LearningPathProgress,
    LearningPathWord,
)


# ---------------------------------------------------------------------------
# Path reads
# ---------------------------------------------------------------------------
def list_active_paths(db: Session) -> list[LearningPath]:
    return (
        db.query(LearningPath)
        .filter(LearningPath.is_active.is_(True))
        .order_by(LearningPath.id.asc())
        .all()
    )


def get_path_by_slug(db: Session, slug: str) -> LearningPath | None:
    return db.query(LearningPath).filter(LearningPath.slug == slug).first()


def get_path_by_goal(db: Session, goal: str) -> LearningPath | None:
    """Find the active learning path tied to an onboarding goal.

    Goals (e.g. "IELTS", "Business English") map 1:1 to a path via its
    ``goal_type`` field, so after onboarding we can send the user straight to
    the words for their chosen goal.
    """
    return (
        db.query(LearningPath)
        .filter(
            LearningPath.goal_type == goal,
            LearningPath.is_active.is_(True),
        )
        .order_by(LearningPath.id.asc())
        .first()
    )


def count_path_words(db: Session, path_id: int) -> int:
    return (
        db.query(func.count(LearningPathWord.id))
        .filter(LearningPathWord.learning_path_id == path_id)
        .scalar()
        or 0
    )


def word_counts_for_paths(db: Session) -> dict[int, int]:
    """Return {path_id: word_count} in one query (for the browse list)."""
    rows = (
        db.query(LearningPathWord.learning_path_id, func.count(LearningPathWord.id))
        .group_by(LearningPathWord.learning_path_id)
        .all()
    )
    return {path_id: count for path_id, count in rows}


def list_path_words(
    db: Session, path_id: int, *, limit: int | None = None, offset: int = 0
) -> list[CatalogWord]:
    """Catalog words in a path, ordered by ``order_index``."""
    q = (
        db.query(CatalogWord)
        .join(LearningPathWord, LearningPathWord.word_id == CatalogWord.id)
        .filter(LearningPathWord.learning_path_id == path_id)
        .order_by(LearningPathWord.order_index.asc())
    )
    if offset:
        q = q.offset(offset)
    if limit is not None:
        q = q.limit(limit)
    return q.all()


def get_path_word_at_position(
    db: Session, path_id: int, position: int
) -> CatalogWord | None:
    """The catalog word at a 0-based position within the path's order."""
    if position < 0:
        return None
    rows = list_path_words(db, path_id, limit=1, offset=position)
    return rows[0] if rows else None


def path_word_ids(db: Session, path_id: int) -> list[int]:
    """Catalog word ids in a path, ordered by ``order_index``."""
    rows = (
        db.query(LearningPathWord.word_id)
        .filter(LearningPathWord.learning_path_id == path_id)
        .order_by(LearningPathWord.order_index.asc())
        .all()
    )
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Per-user progress through a path
# ---------------------------------------------------------------------------
def get_progress(
    db: Session, user_id: int, path_id: int
) -> LearningPathProgress | None:
    return (
        db.query(LearningPathProgress)
        .filter(
            LearningPathProgress.user_id == user_id,
            LearningPathProgress.learning_path_id == path_id,
        )
        .first()
    )


def get_or_create_progress(
    db: Session, user_id: int, path_id: int
) -> LearningPathProgress:
    progress = get_progress(db, user_id, path_id)
    if progress is None:
        progress = LearningPathProgress(
            user_id=user_id, learning_path_id=path_id, current_index=0
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)
    return progress


def update_progress_position(
    db: Session, user_id: int, path_id: int, position: int
) -> LearningPathProgress:
    """Remember the word the user is currently studying in a path."""
    progress = get_or_create_progress(db, user_id, path_id)
    if progress.current_index != position:
        progress.current_index = position
        db.commit()
    return progress


def mark_path_completed(
    db: Session, user_id: int, path_id: int
) -> LearningPathProgress:
    progress = get_or_create_progress(db, user_id, path_id)
    progress.completed = True
    progress.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(progress)
    return progress


def count_studied_in_path(db: Session, user_id: int, path_id: int) -> int:
    """How many words in this path the user has saved an answer for."""
    return (
        db.query(func.count(UserWordAnswer.id))
        .join(
            LearningPathWord,
            LearningPathWord.word_id == UserWordAnswer.catalog_word_id,
        )
        .filter(
            LearningPathWord.learning_path_id == path_id,
            UserWordAnswer.user_id == user_id,
        )
        .scalar()
        or 0
    )


def first_unstudied_position(db: Session, user_id: int, path_id: int) -> int | None:
    """0-based position of the first path word the user has NOT answered.

    Used to resume study and to jump to "weak" (skipped) words. Returns None
    when every word in the path has been studied.
    """
    ordered_ids = path_word_ids(db, path_id)
    if not ordered_ids:
        return None
    answered = {
        r[0]
        for r in db.query(UserWordAnswer.catalog_word_id)
        .filter(
            UserWordAnswer.user_id == user_id,
            UserWordAnswer.catalog_word_id.in_(ordered_ids),
        )
        .all()
    }
    for position, word_id in enumerate(ordered_ids):
        if word_id not in answered:
            return position
    return None


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------
def add_words_to_path(
    db: Session, path: LearningPath, words: list[CatalogWord]
) -> int:
    """Attach an ordered list of words to a path (skips ones already linked)."""
    existing = {
        link.word_id
        for link in db.query(LearningPathWord.word_id)
        .filter(LearningPathWord.learning_path_id == path.id)
        .all()
    }
    # Continue ordering after any words already present.
    next_index = count_path_words(db, path.id)
    added = 0
    for word in words:
        if word.id in existing:
            continue
        db.add(
            LearningPathWord(
                learning_path_id=path.id,
                word_id=word.id,
                order_index=next_index,
            )
        )
        existing.add(word.id)
        next_index += 1
        added += 1
    if added:
        db.commit()
    return added


# ---------------------------------------------------------------------------
# The six standard learning paths (name, slug, description, level, goal_type).
# These slugs are the canonical identifiers used in URLs and seeding.
# ---------------------------------------------------------------------------
PATH_BLUEPRINTS = [
    (
        "IELTS Vocabulary Path",
        "ielts",
        "Academic and high-frequency words to prepare for the IELTS exam.",
        "advanced",
        "IELTS",
    ),
    (
        "TOEFL Vocabulary Path",
        "toefl",
        "Academic vocabulary commonly seen in TOEFL reading and writing.",
        "advanced",
        "TOEFL",
    ),
    (
        "YDS / YÖKDİL Vocabulary Path",
        "yds-yokdil",
        "Advanced academic words for Turkey's YDS and YÖKDİL exams.",
        "advanced",
        "YDS / YÖKDİL",
    ),
    (
        "Business English Vocabulary Path",
        "business-english",
        "Practical vocabulary for the workplace and professional life.",
        "intermediate",
        "Business English",
    ),
    (
        "Academic English Vocabulary Path",
        "academic-english",
        "Formal, academic vocabulary for university and research contexts.",
        "advanced",
        "Academic English",
    ),
    (
        "Daily English Vocabulary Path",
        "daily-english",
        "Everyday words to get comfortable with English quickly.",
        "beginner",
        "Daily English",
    ),
]

# Words considered business/professional vocabulary. Whole-word matching keeps
# this precise (e.g. avoids matching "important" for "port").
BUSINESS_WORDS = {
    "business", "company", "corporate", "market", "marketing", "finance",
    "financial", "invest", "investment", "investor", "profit", "revenue",
    "budget", "client", "customer", "contract", "negotiate", "negotiation",
    "salary", "employee", "employer", "manager", "management", "manage",
    "trade", "economy", "economic", "account", "accounting", "sales",
    "purchase", "supply", "demand", "stock", "shares", "shareholder",
    "merger", "strategy", "strategic", "productivity", "deadline", "meeting",
    "project", "invoice", "payment", "bank", "banking", "loan", "capital",
    "asset", "liability", "partnership", "entrepreneur", "commerce",
    "commercial", "retail", "wholesale", "export", "import", "tax", "audit",
    "enterprise", "industry", "industrial", "product", "production", "brand",
    "consumer", "competition", "competitor", "negotiating", "wage", "income",
    "expense", "fund", "funding", "insurance", "mortgage", "tariff", "vendor",
}

# Research / scholarly vocabulary -> Academic English path.
ACADEMIC_WORDS = {
    "analysis", "analyze", "analytical", "theory", "theoretical", "hypothesis",
    "method", "methodology", "research", "data", "evidence", "conclude",
    "conclusion", "abstract", "thesis", "empirical", "paradigm", "framework",
    "concept", "conceptual", "define", "definition", "derive", "infer",
    "interpret", "interpretation", "evaluate", "evaluation", "assess",
    "assessment", "significant", "significance", "variable", "correlation",
    "experiment", "experimental", "observe", "observation", "phenomenon",
    "criteria", "criterion", "context", "structure", "function", "principle",
    "factor", "qualitative", "quantitative", "literature", "citation",
    "journal", "scholar", "scholarly", "academic", "dissertation", "seminar",
    "lecture", "curriculum", "syllabus", "discipline", "cognitive",
    "statistical", "statistics", "sample", "survey", "methodical", "rational",
    "logic", "logical", "argument", "premise", "validity", "reliability",
    "synthesis", "comprehensive", "fundamental", "theoretical", "scientific",
}

# Everyday life vocabulary -> Daily English path.
DAILY_WORDS = {
    "family", "mother", "father", "friend", "food", "eat", "drink", "water",
    "house", "home", "room", "kitchen", "bed", "sleep", "morning", "night",
    "today", "tomorrow", "week", "school", "work", "money", "shop", "buy",
    "walk", "run", "happy", "sad", "love", "like", "time", "day", "year",
    "weather", "rain", "sun", "hot", "cold", "car", "bus", "train", "street",
    "phone", "music", "game", "play", "watch", "read", "write", "talk",
    "help", "clean", "cook", "wash", "open", "close", "child", "baby", "dog",
    "cat", "city", "country", "road", "hour", "minute", "clothes", "shoes",
    "shirt", "hungry", "thirsty", "tired", "sick", "doctor", "hospital",
    "market", "restaurant", "coffee", "tea", "bread", "milk", "egg", "fruit",
    "vegetable", "meat", "dinner", "lunch", "breakfast", "happy", "name",
    "people", "person", "man", "woman", "boy", "girl", "old", "young", "new",
}

# Exam paths share academic vocabulary in real life, but the user wants each
# selection to show DIFFERENT words. The leftover intermediate/advanced pool is
# split deterministically across these slugs so the topical cores never overlap.
EXAM_PARTITION = ["ielts", "toefl", "yds-yokdil", "academic-english"]

# Target number of words per path. Each path keeps its topical words FIRST and
# is then filled up to this size from the shared catalog (so a path can exceed
# its small topical core). With a 10k catalog and 6 paths the fills necessarily
# overlap, but each path's leading words stay on-topic and no two paths are
# identical (different cores + different, rotated fills).
TARGET_PATH_SIZE = 5000


def assign_path_for_word(word: CatalogWord) -> str:
    """Pick the single best path slug for a word.

    Paths are kept disjoint so that choosing Business vs. IELTS vs. Daily (etc.)
    surfaces genuinely different words:

      * Business keywords  -> Business English
      * Academic keywords  -> Academic English
      * Beginner / everyday-> Daily English
      * Everything else (intermediate/advanced exam vocabulary) is split
        deterministically across the exam paths so each shows distinct words.
    """
    word_text = (word.word or "").lower()
    level = (word.level or "").lower()

    if word_text in BUSINESS_WORDS:
        return "business-english"
    if word_text in ACADEMIC_WORDS:
        return "academic-english"
    if level == "beginner" or word_text in DAILY_WORDS:
        return "daily-english"

    # Deterministic, idempotent split (based on the stable catalog id) so the
    # remaining exam vocabulary is divided into non-overlapping slices.
    return EXAM_PARTITION[(word.id or 0) % len(EXAM_PARTITION)]


def assign_paths_for_word(word: CatalogWord) -> set[str]:
    """Backward-compatible wrapper returning a single-element set."""
    return {assign_path_for_word(word)}


def get_or_create_path(db: Session, blueprint: tuple) -> tuple[LearningPath, bool]:
    """Return (path, created) for one blueprint tuple, creating if missing."""
    name, slug, desc, level, goal_type = blueprint
    path = get_path_by_slug(db, slug)
    if path is not None:
        return path, False
    path = LearningPath(
        name=name,
        slug=slug,
        description=desc,
        level=level,
        goal_type=goal_type,
        is_active=True,
    )
    db.add(path)
    db.commit()
    db.refresh(path)
    return path, True


def expected_path_size(db: Session) -> int:
    """Target words per path, capped by how many catalog words exist."""
    total = db.query(func.count(CatalogWord.id)).scalar() or 0
    return min(TARGET_PATH_SIZE, total)


def paths_need_rebuild(db: Session) -> bool:
    """True when the standard paths are missing or not at the expected size.

    This catches both a fresh DB and the old buggy data (wrong sizes / shared
    word sets). After a successful rebuild every path has exactly
    ``expected_path_size`` words, so this returns False on a healthy DB.
    """
    total = db.query(func.count(CatalogWord.id)).scalar() or 0
    if total == 0:
        return False
    expected = min(TARGET_PATH_SIZE, total)
    for _, slug, *_ in PATH_BLUEPRINTS:
        path = get_path_by_slug(db, slug)
        if path is None or count_path_words(db, path.id) != expected:
            return True
    return False


def rebuild_path_words(db: Session) -> dict:
    """Create any missing standard paths, then (re)build their word links.

    Each path is filled to ``TARGET_PATH_SIZE`` words:
      1. its topical core words first (classification preserved at the top);
      2. then filler words from the shared catalog, taken from a path-specific
         rotation so the paths stay distinct even though their fills overlap.

    Existing links are cleared first, so this safely corrects older data and is
    idempotent (re-running yields the same deterministic result).
    """
    paths_by_slug: dict[str, LearningPath] = {}
    paths_created = 0
    for blueprint in PATH_BLUEPRINTS:
        path, created = get_or_create_path(db, blueprint)
        paths_by_slug[path.slug] = path
        if created:
            paths_created += 1

    # Clear existing links so re-assignment cannot leave stale data.
    path_ids = [p.id for p in paths_by_slug.values()]
    db.query(LearningPathWord).filter(
        LearningPathWord.learning_path_id.in_(path_ids)
    ).delete(synchronize_session=False)
    db.commit()

    # Load the catalog once, ordered by id (stable, deterministic).
    all_words = db.query(CatalogWord).order_by(CatalogWord.id.asc()).all()
    total = len(all_words)
    target = min(TARGET_PATH_SIZE, total)
    ordered_slugs = [bp[1] for bp in PATH_BLUEPRINTS]
    num_paths = len(ordered_slugs)

    # Disjoint topical cores (one primary path per word).
    cores: dict[str, list[CatalogWord]] = {slug: [] for slug in paths_by_slug}
    for word in all_words:
        slug = assign_path_for_word(word)
        if slug in cores:
            cores[slug].append(word)

    if total >= num_paths * target:
        # Enough words for fully DISTINCT (non-overlapping) paths. Each path
        # takes its topical core first, capped at ``target``; under-full paths
        # are then filled from the leftover pool so every word lands in exactly
        # one path.
        path_words = _build_disjoint(ordered_slugs, all_words, cores, target)
    else:
        # Not enough words to avoid overlap: keep topical cores first, then fill
        # to ``target`` from a path-specific rotation (paths overlap but stay
        # distinct and on-topic at the top).
        path_words = _build_with_overlap(ordered_slugs, all_words, cores, target)

    links_created = 0
    for slug in ordered_slugs:
        links_created += add_words_to_path(db, paths_by_slug[slug], path_words[slug])

    return {
        "paths_created": paths_created,
        "links_created": links_created,
        "paths_total": len(PATH_BLUEPRINTS),
    }


def _build_disjoint(
    ordered_slugs: list[str],
    all_words: list[CatalogWord],
    cores: dict[str, list[CatalogWord]],
    target: int,
) -> dict[str, list[CatalogWord]]:
    """Partition words so each path gets exactly ``target`` UNIQUE words."""
    result: dict[str, list[CatalogWord]] = {}
    used: set[int] = set()
    for slug in ordered_slugs:
        take = cores[slug][:target]
        result[slug] = list(take)
        used.update(w.id for w in take)

    leftover = [w for w in all_words if w.id not in used]
    li = 0
    for slug in ordered_slugs:
        while len(result[slug]) < target and li < len(leftover):
            result[slug].append(leftover[li])
            li += 1
    return result


def _build_with_overlap(
    ordered_slugs: list[str],
    all_words: list[CatalogWord],
    cores: dict[str, list[CatalogWord]],
    target: int,
) -> dict[str, list[CatalogWord]]:
    """Fill each path to ``target`` (core first), allowing shared filler words."""
    total = len(all_words)
    result: dict[str, list[CatalogWord]] = {}
    for index, slug in enumerate(ordered_slugs):
        ordered = list(cores[slug])
        chosen_ids = {w.id for w in ordered}
        if len(ordered) < target and total:
            offset = (index * total // len(ordered_slugs)) % total
            rotated = all_words[offset:] + all_words[:offset]
            for word in rotated:
                if len(ordered) >= target:
                    break
                if word.id in chosen_ids:
                    continue
                ordered.append(word)
                chosen_ids.add(word.id)
        result[slug] = ordered[:target]
    return result


def seed_learning_paths(db: Session, *, force: bool = False) -> dict:
    """Create the six standard paths and link catalog words to them (disjoint).

    Self-healing and idempotent:
      * Fresh DB        -> creates paths and assigns words.
      * Already seeded  -> skips (cheap) unless a rebuild is needed.
      * Buggy overlap   -> rebuilds automatically (old data is corrected).
      * ``force=True``  -> always rebuilds (used by the CLI).

    Returns a summary: ``paths_created``, ``links_created``, ``paths_total``.
    """
    if db.query(CatalogWord.id).first() is None:
        return {
            "paths_created": 0,
            "links_created": 0,
            "paths_total": len(PATH_BLUEPRINTS),
            "note": "no catalog words to build paths from",
        }

    existing_slugs = {s for (s,) in db.query(LearningPath.slug).all()}
    target_slugs = {bp[1] for bp in PATH_BLUEPRINTS}
    fully_seeded = target_slugs.issubset(existing_slugs)

    if fully_seeded and not force and not paths_need_rebuild(db):
        return {
            "paths_created": 0,
            "links_created": 0,
            "paths_total": len(PATH_BLUEPRINTS),
            "note": "already seeded",
        }

    return rebuild_path_words(db)


# Backward-compatible alias: startup and older callers use this name.
def seed_default_paths(db: Session) -> dict:
    """Deprecated name kept for compatibility; seeds the standard paths."""
    return seed_learning_paths(db)
