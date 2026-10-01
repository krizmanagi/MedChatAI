"""Safety layer: emergency / crisis detection and personal-identifier redaction.

These checks run *before* the question reaches the language model:

* **Emergency detection** flags red-flag phrasing (e.g. crushing chest pain,
  stroke signs, trouble breathing) so the UI can show an urgent-care banner
  regardless of what the model says.
* **Crisis detection** catches self-harm language and returns crisis-line
  information immediately.
* **Redaction** strips obvious personal identifiers (emails, phone numbers,
  SSNs, dates of birth, record numbers) so they are never sent to the model.

This is a best-effort safeguard, not a compliance guarantee.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

EMERGENCY_PATTERNS: list[tuple[str, str]] = [
    (r"\b(crushing|severe|sudden|radiating)\b.{0,30}\bchest (pain|pressure|tightness)\b", "Severe or sudden chest pain"),
    (r"\bchest (pain|pressure|tightness)\b.{0,40}\b(arm|jaw|sweat|sweating|short of breath|shortness of breath)\b", "Chest pain with other warning signs"),
    (r"\b(having|think i'?m having|having a) (a )?heart attack\b", "Possible heart attack"),
    (r"\b(can'?t|cannot|unable to) breathe\b|\bstruggling to breathe\b|\blips? (are |is )?(turning )?blue\b", "Severe trouble breathing"),
    (r"\b(face|facial) (is )?droop|\bslurred speech\b|\bsudden(ly)? (numb|weak)|\bweak(ness)? on one side\b|\bhaving a stroke\b", "Possible stroke signs"),
    (r"\b(worst headache of my life|thunderclap headache)\b", "Sudden severe headache"),
    (r"\b(unconscious|unresponsive|won'?t wake up|not breathing)\b", "Unresponsive person"),
    (r"\b(seizure|seizing|convulsing)\b.{0,30}\b(won'?t stop|not stopping|first time|minutes)\b", "Prolonged or first seizure"),
    (r"\b(throat|tongue) (is )?(swelling|closing)\b|\banaphyla", "Possible severe allergic reaction"),
    (r"\b(overdose|overdosed|took too many)\b", "Possible overdose"),
    (r"\b(vomiting|coughing up|throwing up) blood\b|\bbleeding (that )?(won'?t|will not) stop\b", "Severe bleeding"),
]

CRISIS_PATTERNS = [
    r"\b(kill|hurt|harm) (myself|me)\b",
    r"\bsuicid(e|al)\b",
    r"\bend (it all|my life|my own life)\b",
    r"\b(take|taking) my (own )?life\b",
    r"\bwant to die\b",
    r"\bdon'?t want to (live|be alive)\b",
    r"\bself[- ]?harm\b",
]

EMERGENCY_MESSAGE = (
    "Some of what you described can be a sign of a medical emergency. "
    "If this is happening now, call 911 (or your local emergency number) or go to the nearest emergency department. "
    "Do not wait for an online answer."
)

CRISIS_MESSAGE = (
    "I'm really sorry you're going through this. You don't have to handle it alone. "
    "If you're in the U.S., you can call or text 988 to reach the Suicide & Crisis Lifeline, any time, day or night. "
    "If you're elsewhere, please contact your local emergency number or a local crisis line. "
    "If you're in immediate danger, call 911 now. "
    "If it would help, I'm happy to keep talking, and a trusted person or a clinician can also support you."
)

PII_PATTERNS: list[tuple[str, str]] = [
    ("EMAIL", r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    ("SSN", r"\b\d{3}-\d{2}-\d{4}\b"),
    ("PHONE", r"(?<!\w)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b"),
    ("DATE_OF_BIRTH", r"\b(?:dob|date of birth|born on)\s*:?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),
    ("RECORD_NUMBER", r"\b(?:mrn|medical record( number)?|patient id|member id)\s*[:#]?\s*[A-Z0-9-]{4,}\b"),
]


@dataclass
class SafetyReport:
    emergency: bool = False
    emergency_reasons: list[str] = field(default_factory=list)
    crisis: bool = False
    redactions: list[str] = field(default_factory=list)
    sanitized_text: str = ""

    def to_dict(self) -> dict:
        return {
            "emergency": self.emergency,
            "emergency_reasons": self.emergency_reasons,
            "crisis": self.crisis,
            "redactions": self.redactions,
        }


def redact_pii(text: str) -> tuple[str, list[str]]:
    found: list[str] = []
    for label, pattern in PII_PATTERNS:
        text, n = re.subn(pattern, f"[{label}]", text, flags=re.IGNORECASE)
        if n:
            found.append(label)
    return text, found


def assess(text: str, redact: bool = True) -> SafetyReport:
    lowered = text.lower()
    report = SafetyReport(sanitized_text=text)

    for pattern, reason in EMERGENCY_PATTERNS:
        if re.search(pattern, lowered) and reason not in report.emergency_reasons:
            report.emergency_reasons.append(reason)
    report.emergency = bool(report.emergency_reasons)
    report.crisis = any(re.search(p, lowered) for p in CRISIS_PATTERNS)

    if redact:
        report.sanitized_text, report.redactions = redact_pii(text)
    return report
