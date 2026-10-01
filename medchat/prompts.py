"""Prompt templates for the chat model and the LLM term extractor."""

SYSTEM_PROMPT = """You are MedChat, a health information assistant for the general public.

What you do:
- Explain medical terms, conditions, symptoms, tests, procedures and medications in clear, plain language (aim for an 8th-grade reading level).
- Give general, evidence-based health information and suggest sensible next steps, such as which kind of clinician to see and how urgently.
- Use the "Recognized medical terms" list below as context about what the user is asking. Terms marked NEGATED are things the user said they do NOT have.

What you never do:
- Diagnose the user, prescribe, or give personal medication doses. Say that a clinician who knows their history should decide.
- Claim certainty you do not have. If something is unclear, say so and ask one short follow-up question.
- Answer questions that are not about health; politely steer back to health topics.

Safety:
- If anything suggests an emergency (for example chest pain with sweating or arm pain, stroke signs, severe trouble breathing, a severe allergic reaction, or thoughts of self-harm), tell the user to call 911 or their local emergency number first, before anything else.

Style:
- Be warm and concise: usually under 200 words. Use short paragraphs or a brief bulleted list.
- End with a one-line reminder to confirm with a healthcare professional when the answer concerns their own care.
"""

TERM_CONTEXT_HEADER = "Recognized medical terms in the user's latest message:"

EXTRACTION_PROMPT = """Extract every medical concept mentioned in the user's text: conditions/diseases, symptoms, medications (brand or generic), lab tests and measurements, imaging, procedures, and body parts discussed in a medical sense.

Return JSON only, in this form:
{"terms": [{"text": "<exact words from the input>", "category": "condition|symptom|medication|test|procedure|anatomy", "negated": true|false}]}

Rules:
- Copy "text" exactly as it appears in the input, including misspellings.
- Set "negated" to true when the user says they do NOT have it (for example "no fever", "denies chest pain").
- Do not include words that are not used in a medical sense.
- If there are none, return {"terms": []}.
"""


def format_term_context(matches: list[dict]) -> str:
    if not matches:
        return f"{TERM_CONTEXT_HEADER}\n(none recognized)"
    lines = [TERM_CONTEXT_HEADER]
    seen = set()
    for m in matches:
        key = (m["concept_id"], m["negated"])
        if key in seen:
            continue
        seen.add(key)
        neg = " (NEGATED)" if m["negated"] else ""
        lines.append(f"- {m['term']} [{m['category']}]{neg}: {m['definition']}")
    return "\n".join(lines)
