"""Cloze-test (boşluk doldurma) deneme sınavı üretici.

SenseWord projesinin 30.000 kelimelik havuzunu (``catalog_words`` tablosu ya da
``app/data/vocabulary_full.json``) kullanarak IELTS, TOEFL, YDS ve e-YDS sınav
formatlarına uygun, çoktan seçmeli "Boşluk Doldurma" deneme sınavları üretir.

Modüler yapı:
    * ``ExamConfig``      -> her sınav türünün süre/şık/kural parametreleri.
    * ``EXAM_CONFIGS``    -> sınav türü -> ExamConfig kayıt defteri.
    * ``WordPool``        -> kelime havuzunu yükler ve çeldirici (distractor)
                             seçimi için indeksler.
    * ``generate_cloze_test`` -> tek bir sınav nesnesi (JSON) üretir.

Komut satırı kullanımı:
    python scripts/exam_generator.py --exam YDS --out exam.json
    python scripts/exam_generator.py --exam IELTS --seed 42
    python scripts/exam_generator.py --all --outdir generated_exams/

Hiçbir harici bağımlılık gerektirmez (yalnızca Python standart kütüphanesi).
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Yol sabitleri
# ---------------------------------------------------------------------------
# scripts/ klasörünün bir üstü = proje kökü (senseword/).
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "senseword.db"
DEFAULT_JSON_PATH = BASE_DIR / "app" / "data" / "vocabulary_full.json"

# Çeldirici/cevap olarak kullanılmaması gereken çok yaygın işlev kelimeleri
# (anlam taşımayan, IELTS/TOEFL kelime sorularında çeldirici değeri düşük).
_FUNCTION_WORDS = {
    "the", "a", "an", "of", "to", "in", "on", "at", "by", "for", "and",
    "or", "but", "if", "is", "are", "was", "were", "be", "been", "am",
    "it", "its", "this", "that", "these", "those", "i", "you", "he",
    "she", "we", "they", "as", "so", "do", "does", "did",
}

A_TO_E = ["A", "B", "C", "D", "E"]


# ---------------------------------------------------------------------------
# Step 1: Veri yapısı tasarımı — ExamConfig
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ExamConfig:
    """Tek bir sınav türünün süresi, şık sayısı ve kurallarını tutar."""

    exam_type: str
    display_name: str
    total_minutes: int                 # Sınavın (ilgili bölümün) toplam süresi.
    num_passages: int                  # Üretilecek okuma parçası sayısı.
    questions_per_passage: int         # Her parçadaki boşluk (soru) sayısı.
    num_options: int                   # Şık sayısı (IELTS/TOEFL 4, YDS/e-YDS 5).
    recommended_minutes_per_passage: int
    delivery: str                      # "paper" | "computer" | "paper_or_computer"
    negative_marking: bool             # Yanlış doğruyu götürür mü?
    preferred_levels: tuple[str, ...]  # Kelime seçiminde tercih edilen seviyeler.
    rules: list[str] = field(default_factory=list)          # İnsan-okur kurallar.
    ui_simulation: dict = field(default_factory=dict)       # Arayüz davranış bayrakları.

    @property
    def total_questions(self) -> int:
        return self.num_passages * self.questions_per_passage

    @property
    def option_labels(self) -> list[str]:
        return A_TO_E[: self.num_options]


# Sınav türü -> yapılandırma kayıt defteri.
EXAM_CONFIGS: dict[str, ExamConfig] = {
    "IELTS": ExamConfig(
        exam_type="IELTS",
        display_name="IELTS Academic/General Reading — Cloze Test",
        total_minutes=60,
        num_passages=3,
        questions_per_passage=10,
        num_options=4,
        recommended_minutes_per_passage=20,
        delivery="paper_or_computer",
        negative_marking=False,
        preferred_levels=("intermediate", "advanced"),
        rules=[
            "Yanlış cevap doğruyu götürmez.",
            "Okuma bölümü toplam 60 dakikadır; her parça için önerilen süre ~20 dakikadır.",
            "Cevaplar akademik/genel bir pasaj bağlamından çıkarılır.",
            "Her soru 4 seçeneklidir (A, B, C, D).",
        ],
    ),
    "TOEFL": ExamConfig(
        exam_type="TOEFL",
        display_name="TOEFL iBT Reading — Vocabulary in Context (Cloze)",
        total_minutes=35,
        num_passages=2,
        questions_per_passage=10,
        num_options=4,
        recommended_minutes_per_passage=17,
        delivery="computer",
        negative_marking=False,
        preferred_levels=("advanced",),
        rules=[
            "Yanlış cevap doğruyu götürmez.",
            "Bilgisayar tabanlıdır; Reading bölümü ~35 dakikadır (genellikle 2 pasaj).",
            "Sorular kelimenin bağlam içindeki anlamına odaklanır.",
            "Her soru 4 seçeneklidir (A, B, C, D).",
        ],
    ),
    "YDS": ExamConfig(
        exam_type="YDS",
        display_name="YDS — Cloze Test Bölümü",
        total_minutes=180,
        num_passages=2,
        questions_per_passage=5,
        num_options=5,
        recommended_minutes_per_passage=10,
        delivery="paper",
        negative_marking=False,
        preferred_levels=("intermediate", "advanced"),
        rules=[
            "Yanlış cevap doğruyu götürmez.",
            "Sınav toplam 180 dakikadır; Cloze Test bölümü (10 soru) için ideal süre 15-20 dakikadır.",
            "Kağıt-kalem sınavıdır.",
            "Gramer, bağlaç ve kelime bilgisi karma sorulur.",
            "Her soru 5 seçeneklidir (A, B, C, D, E).",
            "Genellikle 5'er soruluk 2 okuma parçası (toplam 10 boşluk) içerir.",
        ],
    ),
    "E-YDS": ExamConfig(
        exam_type="E-YDS",
        display_name="e-YDS (Elektronik YDS) — Cloze Test Bölümü",
        total_minutes=180,
        num_passages=2,
        questions_per_passage=5,
        num_options=5,
        recommended_minutes_per_passage=10,
        delivery="computer",
        negative_marking=False,
        preferred_levels=("intermediate", "advanced"),
        rules=[
            "Yanlış cevap doğruyu götürmez.",
            "Sınav toplam 180 dakikadır; içerik ve format YDS ile aynıdır.",
            "Bilgisayar üzerinde ekrandan çözülür, süre dijital olarak akar.",
            "Her soru 5 seçeneklidir (A, B, C, D, E).",
        ],
        ui_simulation={
            "pause_allowed": False,           # "Süreyi Duraklatma Yok"
            "mark_for_review": True,          # Soru işaretleme
            "navigate_back": True,            # Geri dönebilme
            "digital_timer": True,            # Süre dijital akar
        },
    ),
}

# Esnek isimlendirme için takma adlar (büyük/küçük harf duyarsız).
_ALIASES = {
    "EYDS": "E-YDS",
    "E_YDS": "E-YDS",
    "ELECTRONIC-YDS": "E-YDS",
    "TOEFL-IBT": "TOEFL",
    "TOEFLIBT": "TOEFL",
}


def resolve_exam_type(name: str) -> str:
    """Kullanıcı girdisini geçerli bir sınav türü anahtarına çevirir."""
    key = name.strip().upper().replace(" ", "")
    key = _ALIASES.get(key, key)
    if key not in EXAM_CONFIGS:
        valid = ", ".join(EXAM_CONFIGS)
        raise ValueError(f"Bilinmeyen sınav türü: {name!r}. Geçerli türler: {valid}")
    return key


# ---------------------------------------------------------------------------
# Step 1 (devam): Kelime havuzu — WordPool
# ---------------------------------------------------------------------------
@dataclass
class Word:
    """Havuzdaki tek bir kelime kaydı."""

    word: str
    turkish: str
    pronunciation: str
    example_sentence: str
    example_sentence_tr: str
    level: str
    word_type: str | None


class WordPool:
    """30.000 kelimelik havuzu yükler ve soru üretimi için indeksler.

    Kaynak olarak önce SQLite veritabanı (``catalog_words``), bulunamazsa
    ``vocabulary_full.json`` kullanılır. Çeldirici seçimini hızlandırmak için
    kelimeler seviyeye göre gruplanır.
    """

    def __init__(self, words: list[Word]):
        self.words = words
        # Seviye -> kelime listesi (çeldiriciler için hızlı erişim).
        self.by_level: dict[str, list[Word]] = {}
        for w in words:
            self.by_level.setdefault(w.level, []).append(w)
        # Cevap olarak kullanılabilecek (boşluk açılabilen) kelimeler.
        self._answer_pool_cache: dict[tuple[str, ...], list[Word]] = {}

    # ---- Yükleyiciler -----------------------------------------------------
    @classmethod
    def load(
        cls,
        db_path: Path | None = None,
        json_path: Path | None = None,
    ) -> "WordPool":
        db_path = db_path or DEFAULT_DB_PATH
        json_path = json_path or DEFAULT_JSON_PATH
        if db_path.exists():
            try:
                return cls.from_db(db_path)
            except sqlite3.Error:
                pass  # DB okunamazsa JSON'a düş.
        if json_path.exists():
            return cls.from_json(json_path)
        raise FileNotFoundError(
            f"Kelime havuzu bulunamadı. Aranan yerler:\n  - {db_path}\n  - {json_path}"
        )

    @classmethod
    def from_db(cls, db_path: Path) -> "WordPool":
        con = sqlite3.connect(str(db_path))
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                """
                SELECT word, turkish_translation, pronunciation,
                       example_sentence, example_sentence_tr, level, word_type
                FROM catalog_words
                """
            ).fetchall()
        finally:
            con.close()
        words = [
            Word(
                word=r["word"],
                turkish=r["turkish_translation"] or "",
                pronunciation=r["pronunciation"] or "",
                example_sentence=r["example_sentence"] or "",
                example_sentence_tr=r["example_sentence_tr"] or "",
                level=r["level"] or "intermediate",
                word_type=r["word_type"],
            )
            for r in rows
        ]
        return cls(words)

    @classmethod
    def from_json(cls, json_path: Path) -> "WordPool":
        data = json.loads(json_path.read_text(encoding="utf-8"))
        words = [
            Word(
                word=d["word"],
                turkish=d.get("turkish_translation", ""),
                pronunciation=d.get("pronunciation", ""),
                example_sentence=d.get("example_sentence", "") or "",
                example_sentence_tr=d.get("example_sentence_tr", "") or "",
                level=d.get("level", "intermediate"),
                word_type=d.get("word_type"),
            )
            for d in data
        ]
        return cls(words)

    # ---- Seçim yardımcıları ----------------------------------------------
    def answer_candidates(
        self, levels: Iterable[str], *, require_real_sentence: bool = False
    ) -> list[Word]:
        """Boşluk açılabilen (kendi örnek cümlesinde geçen) anlamlı kelimeler.

        Belirtilen seviyelerden, tek sözcüklü, işlev kelimesi olmayan ve örnek
        cümlesinde geçen kelimeleri döndürür.

        ``require_real_sentence=True`` ise jenerik ("This is an example...")
        kalıbındaki cümleler elenir; böylece sorular gerçek bağlamlı olur.
        """
        levels = tuple(levels)
        cache_key = (levels, require_real_sentence)
        if cache_key in self._answer_pool_cache:
            return self._answer_pool_cache[cache_key]

        pool: list[Word] = []
        wanted = set(levels)
        for w in self.words:
            if w.level not in wanted:
                continue
            lw = w.word.lower()
            if " " in w.word or len(lw) < 3 or lw in _FUNCTION_WORDS:
                continue
            if not _word_in_sentence(w.word, w.example_sentence):
                continue
            if require_real_sentence and _is_generic_sentence(w.example_sentence):
                continue
            pool.append(w)
        self._answer_pool_cache[cache_key] = pool
        return pool

    def pick_distractors(
        self,
        answer: Word,
        count: int,
        rng: random.Random,
    ) -> list[str]:
        """Cevaba mantıklı ama yanlış ``count`` adet çeldirici seç.

        Heuristik: aynı seviye + benzer uzunluk (±3) + (varsa) aynı sözcük türü
        olan kelimeler tercih edilir. Yeterli aday yoksa kısıtlar gevşetilir.
        """
        answer_lower = answer.word.lower()
        chosen: list[str] = []
        seen: set[str] = {answer_lower}

        def add_from(candidates: list[Word]) -> None:
            rng.shuffle(candidates)
            for c in candidates:
                if len(chosen) >= count:
                    break
                cl = c.word.lower()
                if cl in seen or " " in c.word:
                    continue
                seen.add(cl)
                chosen.append(c.word)

        same_level = self.by_level.get(answer.level, [])
        target_len = len(answer.word)

        # 1) Aynı seviye + benzer uzunluk + aynı tür (en güçlü çeldiriciler).
        tier1 = [
            c for c in same_level
            if abs(len(c.word) - target_len) <= 3
            and c.word.lower() not in _FUNCTION_WORDS
            and (answer.word_type is None or c.word_type == answer.word_type)
        ]
        add_from(tier1)

        # 2) Aynı seviye + benzer uzunluk (tür kısıtı kaldırıldı).
        if len(chosen) < count:
            tier2 = [
                c for c in same_level
                if abs(len(c.word) - target_len) <= 3
                and c.word.lower() not in _FUNCTION_WORDS
            ]
            add_from(tier2)

        # 3) Aynı seviyeden herhangi biri.
        if len(chosen) < count:
            add_from(list(same_level))

        # 4) Son çare: tüm havuzdan.
        if len(chosen) < count:
            add_from(list(self.words))

        return chosen[:count]


# ---------------------------------------------------------------------------
# Yardımcı metin fonksiyonları
# ---------------------------------------------------------------------------
def _word_in_sentence(word: str, sentence: str) -> bool:
    if not sentence:
        return False
    return re.search(rf"\b{re.escape(word)}\b", sentence, re.IGNORECASE) is not None


def _is_generic_sentence(sentence: str) -> bool:
    """True for placeholder sentences like 'This is an example with the word "x".'."""
    return sentence.strip().lower().startswith("this is an example")


def _blank_sentence(word: str, sentence: str, blank_token: str) -> str:
    """Cümledeki kelimenin tüm tam-sözcük geçişlerini boşlukla değiştirir."""
    return re.sub(
        rf"\b{re.escape(word)}\b",
        blank_token,
        sentence,
        flags=re.IGNORECASE,
    )


# ---------------------------------------------------------------------------
# Step 2: Dinamik soru üretim fonksiyonu
# ---------------------------------------------------------------------------
def _build_question(
    answer: Word,
    number: int,
    blank_no: int,
    config: ExamConfig,
    pool: WordPool,
    rng: random.Random,
) -> dict:
    """Tek bir çoktan seçmeli cloze sorusu üretir (JSON-uyumlu sözlük)."""
    blank_token = "______"
    stem = _blank_sentence(answer.word, answer.example_sentence, blank_token)

    distractors = pool.pick_distractors(answer, config.num_options - 1, rng)
    option_texts = distractors + [answer.word]
    rng.shuffle(option_texts)

    labels = config.option_labels
    options = [{"label": labels[i], "text": txt} for i, txt in enumerate(option_texts)]
    answer_label = next(o["label"] for o in options if o["text"] == answer.word)

    return {
        "number": number,
        "blank_no": blank_no,
        "stem": stem,
        "options": options,
        "answer": answer_label,
        "answer_text": answer.word,
        "explanation": (
            f"Doğru cevap '{answer.word}'. "
            f"Türkçe karşılığı: {answer.turkish or '—'}. "
            f"Telaffuz: {answer.pronunciation or '—'}."
        ),
        "meta": {
            "level": answer.level,
            "word_type": answer.word_type,
            "turkish": answer.turkish,
            "pronunciation": answer.pronunciation,
            "source_sentence": answer.example_sentence,
            "source_sentence_tr": answer.example_sentence_tr,
        },
    }


def generate_cloze_test(
    exam_type: str,
    pool: WordPool | None = None,
    seed: int | None = None,
    num_passages: int | None = None,
    questions_per_passage: int | None = None,
    require_real_sentence: bool = False,
) -> dict:
    """Belirtilen sınav türü için tam bir cloze deneme sınavı üretir.

    Args:
        exam_type: "IELTS", "TOEFL", "YDS" veya "E-YDS" (takma adlar desteklenir).
        pool: Önceden yüklenmiş WordPool; verilmezse otomatik yüklenir.
        seed: Tekrarlanabilirlik için rastgelelik tohumu.
        num_passages / questions_per_passage: Varsayılan yapılandırmayı geçersiz
            kılmak için (isteğe bağlı).

    Returns:
        JSON'a serileştirilebilir sınav nesnesi (dict).
    """
    key = resolve_exam_type(exam_type)
    config = EXAM_CONFIGS[key]
    rng = random.Random(seed)
    pool = pool or WordPool.load()

    n_passages = num_passages or config.num_passages
    n_per_passage = questions_per_passage or config.questions_per_passage
    total_needed = n_passages * n_per_passage

    candidates = pool.answer_candidates(
        config.preferred_levels, require_real_sentence=require_real_sentence
    )
    if len(candidates) < total_needed:
        # Tercih edilen seviyelerde yeterli yoksa tüm seviyelere genişlet.
        candidates = pool.answer_candidates(
            ("beginner", "intermediate", "advanced"),
            require_real_sentence=require_real_sentence,
        )
    if require_real_sentence and len(candidates) < total_needed:
        # Gerçek cümle kısıtıyla yeterli yoksa kısıtı gevşet (jeneriklere izin ver).
        candidates = pool.answer_candidates(
            ("beginner", "intermediate", "advanced")
        )
    if len(candidates) < total_needed:
        raise ValueError(
            f"Havuzda yeterli uygun kelime yok: {len(candidates)} < {total_needed}"
        )

    selected = rng.sample(candidates, total_needed)

    sections = []
    answer_key: dict[str, str] = {}
    q_number = 0
    for p in range(n_passages):
        passage_words = selected[p * n_per_passage : (p + 1) * n_per_passage]
        questions = []
        passage_lines = []
        for blank_no, w in enumerate(passage_words, start=1):
            q_number += 1
            q = _build_question(w, q_number, blank_no, config, pool, rng)
            questions.append(q)
            answer_key[str(q_number)] = q["answer"]
            # Parça metni: boşluklar numaralandırılarak birleştirilir.
            numbered = _blank_sentence(
                w.word, w.example_sentence, f"__({q_number})__"
            )
            passage_lines.append(numbered)

        sections.append(
            {
                "section_no": p + 1,
                "title": f"Passage {p + 1}",
                "recommended_minutes": config.recommended_minutes_per_passage,
                "passage": " ".join(passage_lines),
                "questions": questions,
            }
        )

    return {
        "exam_id": str(uuid.uuid4()),
        "exam_type": config.exam_type,
        "display_name": config.display_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "config": {
            "total_minutes": config.total_minutes,
            "num_options": config.num_options,
            "option_labels": config.option_labels,
            "negative_marking": config.negative_marking,
            "delivery": config.delivery,
            "recommended_minutes_per_passage": config.recommended_minutes_per_passage,
            "ui_simulation": config.ui_simulation,
        },
        "instructions": config.rules,
        "sections": sections,
        "answer_key": answer_key,
        "summary": {
            "num_passages": n_passages,
            "questions_per_passage": n_per_passage,
            "total_questions": total_needed,
            "total_minutes": config.total_minutes,
        },
    }


# ---------------------------------------------------------------------------
# Komut satırı arayüzü
# ---------------------------------------------------------------------------
def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SenseWord kelime havuzundan cloze deneme sınavı üretir.",
    )
    parser.add_argument(
        "--exam",
        help="Sınav türü: IELTS | TOEFL | YDS | E-YDS",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Tüm sınav türleri için birer sınav üret.",
    )
    parser.add_argument("--seed", type=int, default=None, help="Rastgelelik tohumu.")
    parser.add_argument(
        "--passages", type=int, default=None, help="Parça sayısını geçersiz kıl."
    )
    parser.add_argument(
        "--questions-per-passage",
        type=int,
        default=None,
        help="Parça başına soru sayısını geçersiz kıl.",
    )
    parser.add_argument("--out", help="Tek sınav için çıktı JSON dosyası.")
    parser.add_argument(
        "--outdir", help="--all ile: sınavların yazılacağı klasör."
    )
    parser.add_argument("--db", help="SQLite veritabanı yolu (varsayılan: senseword.db).")
    parser.add_argument("--json", dest="json_path", help="vocabulary_full.json yolu.")
    parser.add_argument(
        "--indent", type=int, default=2, help="JSON girinti seviyesi (0 = tek satır)."
    )
    args = parser.parse_args(argv)

    if not args.exam and not args.all:
        parser.error("--exam ya da --all belirtmelisiniz.")

    pool = WordPool.load(
        db_path=Path(args.db) if args.db else None,
        json_path=Path(args.json_path) if args.json_path else None,
    )
    print(f"[i] Kelime havuzu yüklendi: {len(pool.words):,} kelime", file=sys.stderr)

    indent = args.indent or None

    def build(exam_type: str) -> dict:
        return generate_cloze_test(
            exam_type,
            pool=pool,
            seed=args.seed,
            num_passages=args.passages,
            questions_per_passage=args.questions_per_passage,
        )

    if args.all:
        outdir = Path(args.outdir or BASE_DIR / "generated_exams")
        outdir.mkdir(parents=True, exist_ok=True)
        for exam_type in EXAM_CONFIGS:
            exam = build(exam_type)
            path = outdir / f"{_slug(exam_type)}_{exam['exam_id'][:8]}.json"
            path.write_text(
                json.dumps(exam, ensure_ascii=False, indent=indent), encoding="utf-8"
            )
            print(
                f"[+] {exam_type}: {exam['summary']['total_questions']} soru -> {path}",
                file=sys.stderr,
            )
        return 0

    exam = build(args.exam)
    payload = json.dumps(exam, ensure_ascii=False, indent=indent)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(
            f"[+] {exam['exam_type']}: {exam['summary']['total_questions']} soru -> {args.out}",
            file=sys.stderr,
        )
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
