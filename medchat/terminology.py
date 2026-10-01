"""Medical terminology recognition.

Finds medical concepts in free text and maps each one to a canonical concept in
the lexicon (``data/medical_lexicon.json``). The recognizer is deterministic and
runs locally, so it works without any API key and can be evaluated
reproducibly.

Matching strategy, in order of precedence:

1. **Exact lexicon match** on canonical terms, synonyms and lay phrasings.
   All surface forms are compiled into one regular expression, longest first,
   so "type 2 diabetes" wins over "diabetes" and "heart attack" over "heart".
   Spaces and hyphens are interchangeable ("x-ray" == "x ray"), and simple
   plurals are accepted.
2. **Abbreviations** ("HTN", "UTI"). Abbreviations that collide with ordinary
   words ("MS", "PE", "CA") only match in upper case.
3. **Fuzzy match** for likely misspellings of single-word terms
   ("diabetis", "ibuprofin"), using character-level similarity. Only words of
   six or more letters are considered, to limit false positives.

Each match is also checked for **negation** ("no fever", "denies chest pain")
with a small NegEx-style rule set, so downstream code can tell the difference
between a symptom someone has and one they ruled out.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

DEFAULT_LEXICON_PATH = Path(__file__).resolve().parent.parent / "data" / "medical_lexicon.json"

# Words preceding a term (within the same clause) that negate it.
NEGATION_TRIGGERS = (
    "no", "not", "without", "denies", "denied", "deny", "never", "none",
    "negative for", "free of", "absence of", "ruled out", "rule out",
    "don't have", "dont have", "do not have", "doesn't have", "does not have",
    "haven't had", "have not had", "no history of", "no signs of", "no sign of",
)
# Tokens that end the negation scope ("no fever but a cough": cough is not negated).
NEGATION_TERMINATORS = ("but", "however", "although", "though", "except", "yet", "and still")
NEGATION_WINDOW = 5  # max tokens between trigger and term

# Common English words that look similar to medical terms and must never be
# fuzzy-matched to them.
FUZZY_STOPWORDS = {
    "should", "though", "through", "thought", "health", "healthy", "really",
    "doctor", "doctors", "better", "started", "starting", "having", "taking",
    "months", "having", "around", "person", "people", "almost", "always",
    "normal", "worried", "worse", "before", "during", "eating", "drinking",
    "stomach", "allergic", "medicine", "medication", "medications", "pressure",
    "symptoms", "symptom", "pharmacy", "hospital", "chronic", "breathing",
    "sleeping", "walking", "running", "exercise", "workout", "hearts", "heated",
    "fevered", "coughed", "tested", "testing", "treated", "treatment", "therapy",
    "surgeon", "nurse", "clinic", "insurance", "anxious", "severe", "slight",
    "painful", "constant", "sudden", "recently", "weekend", "evening", "morning",
}
FUZZY_MIN_LEN = 6
FUZZY_CUTOFF = 0.86


@dataclass(frozen=True)
class Concept:
    id: str
    term: str
    category: str
    definition: str
    synonyms: tuple[str, ...] = ()
    abbreviations: tuple[str, ...] = ()


@dataclass
class TermMatch:
    concept_id: str
    term: str            # canonical name
    category: str
    text: str            # exact text as written by the user
    start: int
    end: int
    match_type: str      # "exact" | "abbreviation" | "fuzzy"
    confidence: float
    negated: bool = False
    definition: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RecognitionResult:
    text: str
    matches: list[TermMatch] = field(default_factory=list)

    @property
    def concept_ids(self) -> list[str]:
        """Unique concept ids, in order of first appearance."""
        seen: dict[str, None] = {}
        for m in self.matches:
            seen.setdefault(m.concept_id, None)
        return list(seen)

    def to_dict(self) -> dict:
        return {
            "matches": [m.to_dict() for m in self.matches],
            "concept_ids": self.concept_ids,
        }


def _surface_pattern(surface: str) -> str:
    """Regex for one surface form: spaces/hyphens interchangeable, optional apostrophes."""
    parts = re.split(r"[\s\-]+", surface.strip())
    escaped = []
    for p in parts:
        # allow "crohn's" / "crohns" / "crohn’s"
        escaped.append(re.escape(p).replace("'", "['’]?"))
    return r"[\s\-]*".join(escaped) if len(parts) == 1 else r"[\s\-]+".join(escaped)


class TerminologyRecognizer:
    """Recognizes medical concepts in free text using a curated lexicon."""

    def __init__(self, lexicon_path: str | Path = DEFAULT_LEXICON_PATH, enable_fuzzy: bool = True):
        data = json.loads(Path(lexicon_path).read_text(encoding="utf-8"))
        self.version: str = data.get("version", "unknown")
        self.enable_fuzzy = enable_fuzzy
        self.concepts: dict[str, Concept] = {}
        case_sensitive = set(data.get("case_sensitive_abbreviations", []))

        # surface form (lower-cased) -> concept id
        insensitive_forms: dict[str, str] = {}
        sensitive_forms: dict[str, str] = {}

        for raw in data["concepts"]:
            concept = Concept(
                id=raw["id"],
                term=raw["term"],
                category=raw["category"],
                definition=raw.get("definition", ""),
                synonyms=tuple(raw.get("synonyms", [])),
                abbreviations=tuple(raw.get("abbreviations", [])),
            )
            self.concepts[concept.id] = concept
            for form in (concept.term, *concept.synonyms):
                insensitive_forms.setdefault(form.lower(), concept.id)
            for abbr in concept.abbreviations:
                if abbr in case_sensitive:
                    sensitive_forms.setdefault(abbr, concept.id)
                else:
                    insensitive_forms.setdefault(abbr.lower(), concept.id)

        self._forms = insensitive_forms
        self._abbr_forms = {k.lower(): v for k, v in sensitive_forms.items()}
        self._abbrev_lookup = {a.lower() for c in self.concepts.values() for a in c.abbreviations}

        self._insensitive_re = self._compile(insensitive_forms, flags=re.IGNORECASE)
        self._sensitive_re = self._compile(sensitive_forms, flags=0) if sensitive_forms else None

        # single-word forms eligible for fuzzy matching
        self._fuzzy_vocab = {
            form: cid for form, cid in insensitive_forms.items()
            if " " not in form and "-" not in form and len(form) >= FUZZY_MIN_LEN
        }

    @staticmethod
    def _compile(forms: dict[str, str], flags: int) -> re.Pattern:
        ordered = sorted(forms, key=len, reverse=True)
        alternation = "|".join(f"(?:{_surface_pattern(f)})" for f in ordered)
        # optional plural suffix; word boundaries that also respect hyphens/apostrophes
        return re.compile(rf"(?<![\w'’])(?:{alternation})(?:e?s)?(?![\w'’])", flags)

    # ------------------------------------------------------------------ public

    def recognize(self, text: str) -> RecognitionResult:
        matches: list[TermMatch] = []
        taken: list[tuple[int, int]] = []

        def overlaps(start: int, end: int) -> bool:
            return any(start < e and end > s for s, e in taken)

        # 1. exact phrases (case-insensitive) and case-insensitive abbreviations
        for m in self._insensitive_re.finditer(text):
            cid = self._resolve(m.group(0), self._forms)
            if cid is None:
                continue
            norm = self._normalize(m.group(0))
            is_abbr = norm in self._abbrev_lookup or norm.rstrip("s") in self._abbrev_lookup
            matches.append(self._make(cid, m, "abbreviation" if is_abbr else "exact", 0.95 if is_abbr else 1.0))
            taken.append(m.span())

        # 2. case-sensitive abbreviations ("MS", "PE", ...)
        if self._sensitive_re is not None:
            for m in self._sensitive_re.finditer(text):
                if overlaps(*m.span()):
                    continue
                cid = self._resolve(m.group(0), self._abbr_forms)
                if cid is None:
                    continue
                matches.append(self._make(cid, m, "abbreviation", 0.9))
                taken.append(m.span())

        # 3. fuzzy single words (likely misspellings)
        if self.enable_fuzzy:
            for m in re.finditer(r"[A-Za-z][A-Za-z']+", text):
                word = m.group(0).lower()
                if len(word) < FUZZY_MIN_LEN or word in FUZZY_STOPWORDS or overlaps(*m.span()):
                    continue
                best = difflib.get_close_matches(word, self._fuzzy_vocab.keys(), n=1, cutoff=FUZZY_CUTOFF)
                if best:
                    ratio = difflib.SequenceMatcher(None, word, best[0]).ratio()
                    matches.append(self._make(self._fuzzy_vocab[best[0]], m, "fuzzy", round(ratio * 0.9, 3)))
                    taken.append(m.span())

        matches.sort(key=lambda x: x.start)
        for match in matches:
            match.negated = self._is_negated(text, match.start)
        return RecognitionResult(text=text, matches=matches)

    def get(self, concept_id: str) -> Concept | None:
        return self.concepts.get(concept_id)

    # ----------------------------------------------------------------- helpers

    @staticmethod
    def _normalize(s: str) -> str:
        s = s.lower().replace("’", "'")
        return re.sub(r"[\s\-]+", " ", s).strip()

    def _resolve(self, matched: str, table: dict[str, str]) -> str | None:
        norm = self._normalize(matched)
        candidates = [norm]
        if norm.endswith("es"):
            candidates.append(norm[:-2])
        if norm.endswith("s"):
            candidates.append(norm[:-1])
        for cand in candidates:
            for variant in (cand, cand.replace("'", "")):
                if variant in table:
                    return table[variant]
                # tolerate apostrophe differences: "crohns" vs "crohn's"
                for form, cid in table.items():
                    if form.replace("'", "") == variant:
                        return cid
        return None

    def _make(self, cid: str, m: re.Match, match_type: str, confidence: float) -> TermMatch:
        c = self.concepts[cid]
        return TermMatch(
            concept_id=cid, term=c.term, category=c.category, text=m.group(0),
            start=m.start(), end=m.end(), match_type=match_type,
            confidence=confidence, definition=c.definition,
        )

    @staticmethod
    def _is_negated(text: str, start: int) -> bool:
        # Look back within the current clause only.
        prefix = text[:start]
        clause = re.split(r"[.;:!?\n]|,\s*(?:but|however)\b", prefix)[-1].lower()
        tokens = re.findall(r"[a-z']+", clause)
        window = tokens[-(NEGATION_WINDOW + 3):]
        joined = " " + " ".join(window) + " "
        # a terminator after the last trigger ends the negation scope
        last_trigger = -1
        for trig in NEGATION_TRIGGERS:
            idx = joined.rfind(f" {trig} ")
            if idx > last_trigger:
                last_trigger = idx
        if last_trigger < 0:
            return False
        after = joined[last_trigger:]
        if any(f" {t} " in after for t in NEGATION_TERMINATORS):
            return False
        words_after_trigger = len(after.split()) - 1
        return words_after_trigger <= NEGATION_WINDOW + 2


@lru_cache(maxsize=1)
def get_recognizer() -> TerminologyRecognizer:
    return TerminologyRecognizer()
