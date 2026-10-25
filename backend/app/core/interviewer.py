"""Deterministic interview question generator and answer evaluator.

This module provides an offline, zero-dependency approach to generating
interview questions and evaluating answers.  It does NOT call any LLM API
and does not require API keys.  All logic is transparent and reproducible.

Algorithm overview
------------------
Question generation
~~~~~~~~~~~~~~~~~~~
Questions are drawn from a curated bank organised by category:

  - ``behavioral``  — situational / competency questions (STAR-method answers).
  - ``technical``   — generic software-engineering fundamentals.
  - ``role_specific`` — questions selected from a role-keyword map that
                        matches the *role_target* field.
  - ``jd_skill``    — one question per skill identified in the job description
                        text (using the same vocabulary as the matcher).

The number of questions per category is configurable but has sensible
defaults.  When a resume or job description is attached, the selection is
refined: skill-gap questions are prioritised so the session focuses on
areas the candidate may need to strengthen.

Answer evaluation
~~~~~~~~~~~~~~~~~
Evaluation is keyword-based and heuristic:

  1. **Keyword coverage** — the evaluator checks how many of the question's
     expected keywords appear in the answer (case-insensitive).
  2. **Length** — very short answers (< 30 words) are flagged as thin.
  3. **Structure cues** — for behavioral questions the evaluator checks for
     STAR-method markers ("situation", "task", "action", "result" or "I …ed").
  4. **Score** — 0–100, computed as:
       keyword_score * 0.5 + length_score * 0.25 + structure_score * 0.25
  5. **Strengths / improvements** — generated from the evaluation result.

Limitations
~~~~~~~~~~~
- Keyword matching cannot assess answer quality, depth, or accuracy.
- The score is a rough heuristic useful for self-reflection, not screening.
- Questions are sampled deterministically (sorted, not randomised) so the
  same input always produces the same session.
- Synonyms and paraphrases are not resolved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Reuse the skill vocabulary from the matcher to extract JD skills
# ---------------------------------------------------------------------------

from app.core.matcher import _extract_skills  # noqa: WPS436

# ---------------------------------------------------------------------------
# Question bank
# ---------------------------------------------------------------------------

# Each entry is (question_text, [expected_keywords])
# Keywords guide the answer evaluator; they do NOT appear in the question.

_BEHAVIORAL_QUESTIONS: list[tuple[str, list[str]]] = [
    (
        "Tell me about a time you faced a difficult technical challenge. How did you approach it?",
        ["challenge", "problem", "solution", "learned", "resolved", "approach"],
    ),
    (
        "Describe a situation where you had to meet a tight deadline. What steps did you take?",
        ["deadline", "priority", "time", "plan", "delivered", "managed"],
    ),
    (
        "Give an example of a time you disagreed with a teammate. How did you handle it?",
        ["disagree", "communicate", "listen", "compromise", "resolved", "team"],
    ),
    (
        "Tell me about a project you are most proud of. What was your contribution?",
        ["contribution", "impact", "built", "designed", "led", "delivered"],
    ),
    (
        "Describe a time you had to learn a new technology quickly. How did you do it?",
        ["learned", "resources", "practice", "applied", "quickly", "documentation"],
    ),
    (
        "Tell me about a mistake you made at work. What did you learn from it?",
        ["mistake", "learned", "improved", "responsibility", "fixed", "next time"],
    ),
    (
        "Describe a situation where you had to collaborate with a difficult colleague.",
        ["collaboration", "communicate", "empathy", "resolved", "team", "outcome"],
    ),
    (
        "Give an example of when you had to prioritise multiple tasks simultaneously.",
        ["prioritise", "organised", "time management", "delivered", "focus", "urgent"],
    ),
    (
        "Tell me about a time you received critical feedback. How did you respond?",
        ["feedback", "improved", "action", "listened", "changed", "growth"],
    ),
    (
        "Describe a situation where you took initiative beyond your assigned responsibilities.",
        ["initiative", "proactive", "ownership", "impact", "extra", "volunteered"],
    ),
]

_TECHNICAL_QUESTIONS: list[tuple[str, list[str]]] = [
    (
        "Explain the difference between SQL and NoSQL databases. When would you choose each?",
        ["sql", "nosql", "structured", "schema", "scalability", "relational", "document"],
    ),
    (
        "What is the purpose of indexing in a database, and what are its trade-offs?",
        ["index", "query", "performance", "write", "storage", "trade-off"],
    ),
    (
        "Describe the REST architectural style and its key constraints.",
        ["rest", "stateless", "resource", "http", "uniform interface", "client-server"],
    ),
    (
        "What is the difference between authentication and authorisation?",
        ["authentication", "authorisation", "identity", "permission", "jwt", "token"],
    ),
    (
        "Explain what a race condition is and how you would prevent one.",
        ["race condition", "concurrency", "lock", "atomic", "thread", "mutex"],
    ),
    (
        "What are the SOLID principles? Give a brief example of one.",
        ["solid", "single responsibility", "open closed", "liskov", "interface", "dependency"],
    ),
    (
        "How does HTTP caching work, and what headers are involved?",
        ["cache", "etag", "max-age", "cache-control", "304", "http"],
    ),
    (
        "What is the difference between a process and a thread?",
        ["process", "thread", "memory", "context switch", "concurrency", "isolation"],
    ),
    (
        "Explain the CAP theorem and its implications for distributed systems.",
        ["cap", "consistency", "availability", "partition tolerance", "distributed"],
    ),
    (
        "What is Big-O notation? Give an example of O(n²) vs O(n log n).",
        ["big-o", "complexity", "n squared", "n log n", "sort", "loop", "algorithm"],
    ),
    (
        "Describe the difference between synchronous and asynchronous programming.",
        ["sync", "async", "await", "event loop", "non-blocking", "callback", "promise"],
    ),
    (
        "What is a microservices architecture? What are its advantages and disadvantages?",
        ["microservices", "service", "deploy", "scale", "independent", "latency", "complexity"],
    ),
]

# Role keyword → list of tailored questions.
# Keys are lowercase substrings matched against role_target.
_ROLE_QUESTIONS: dict[str, list[tuple[str, list[str]]]] = {
    "python": [
        (
            "What is the difference between a list and a tuple in Python?",
            ["list", "tuple", "mutable", "immutable", "hashable", "performance"],
        ),
        (
            "Explain Python's GIL (Global Interpreter Lock) and its impact on concurrency.",
            ["gil", "thread", "cpython", "io-bound", "cpu-bound", "multiprocessing"],
        ),
        (
            "What are Python decorators and when would you use one?",
            ["decorator", "wrapper", "function", "closure", "syntax", "@"],
        ),
        (
            "Explain the difference between *args and **kwargs.",
            ["args", "kwargs", "positional", "keyword", "flexible", "unpack"],
        ),
    ],
    "javascript": [
        (
            "What is the event loop in JavaScript and how does it work?",
            ["event loop", "call stack", "callback queue", "microtask", "promise", "async"],
        ),
        (
            "Explain the difference between `var`, `let`, and `const`.",
            ["var", "let", "const", "scope", "hoisting", "block", "reassign"],
        ),
        (
            "What are closures in JavaScript? Give an example use case.",
            ["closure", "scope", "function", "variable", "encapsulate", "lexical"],
        ),
    ],
    "react": [
        (
            "Explain the difference between state and props in React.",
            ["state", "props", "component", "mutable", "immutable", "data flow"],
        ),
        (
            "What are React hooks? Explain useState and useEffect.",
            ["hook", "usestate", "useeffect", "functional component", "side effect", "dependency"],
        ),
        (
            "How does React's virtual DOM improve performance?",
            ["virtual dom", "reconciliation", "diff", "render", "performance", "batch"],
        ),
    ],
    "backend": [
        (
            "How would you design a RESTful API for a resource like 'User'?",
            ["rest", "endpoint", "http method", "get", "post", "put", "delete", "status code"],
        ),
        (
            "What strategies would you use to improve the performance of a slow database query?",
            ["index", "query plan", "join", "cache", "n+1", "pagination", "explain"],
        ),
    ],
    "frontend": [
        (
            "Explain the difference between SSR (server-side rendering) and CSR (client-side rendering).",
            ["ssr", "csr", "seo", "hydration", "initial load", "javascript", "server"],
        ),
        (
            "What are Web Accessibility (a11y) best practices you apply in your work?",
            ["aria", "semantic html", "alt text", "keyboard", "focus", "contrast", "screen reader"],
        ),
    ],
    "devops": [
        (
            "What is the difference between Continuous Integration and Continuous Deployment?",
            ["ci", "cd", "pipeline", "build", "test", "deploy", "automated"],
        ),
        (
            "Explain the purpose of Docker and how containers differ from virtual machines.",
            ["docker", "container", "image", "vm", "isolation", "lightweight", "os"],
        ),
    ],
    "data": [
        (
            "What is the difference between supervised and unsupervised learning?",
            ["supervised", "unsupervised", "label", "cluster", "classification", "regression"],
        ),
        (
            "Explain overfitting and how you would prevent it.",
            ["overfitting", "regularisation", "cross-validation", "dropout", "generalise", "train"],
        ),
    ],
    "engineer": [
        (
            "How do you approach debugging a production issue you've never seen before?",
            ["logs", "reproduce", "isolate", "monitor", "hypothesis", "root cause", "fix"],
        ),
        (
            "Describe your approach to writing clean, maintainable code.",
            ["readable", "naming", "comments", "tests", "refactor", "review", "solid"],
        ),
    ],
}

# Template for skill-specific questions generated from JD skills
_SKILL_QUESTION_TEMPLATE = (
    "The role requires experience with {skill}. Can you describe a project or "
    "task where you used {skill}, and what the outcome was?"
)


# ---------------------------------------------------------------------------
# Data classes for public API
# ---------------------------------------------------------------------------


@dataclass
class Question:
    """A single interview question.

    Attributes
    ----------
    text:
        The question as shown to the user.
    category:
        One of ``behavioral``, ``technical``, ``role_specific``, ``jd_skill``.
    expected_keywords:
        Internal hint list used by the evaluator.  Not exposed to the client.
    skill_ref:
        For ``jd_skill`` questions: the skill name this question probes.
    """

    text: str
    category: str
    expected_keywords: list[str] = field(default_factory=list)
    skill_ref: str | None = None

    def to_dict(self) -> dict:
        """Serialise for storage in the JSON column."""
        return {
            "text": self.text,
            "category": self.category,
            "expected_keywords": self.expected_keywords,
            "skill_ref": self.skill_ref,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Question":
        """Deserialise from a JSON column value."""
        return cls(
            text=data["text"],
            category=data["category"],
            expected_keywords=data.get("expected_keywords", []),
            skill_ref=data.get("skill_ref"),
        )


@dataclass
class EvaluationResult:
    """The result of evaluating one answer.

    Attributes
    ----------
    score:
        0–100 heuristic score.
    strengths:
        List of positive observations about the answer.
    improvements:
        List of specific suggestions to improve the answer.
    note:
        A brief explanation of the scoring method's limitations.
    """

    score: float
    strengths: list[str]
    improvements: list[str]
    note: str

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "strengths": self.strengths,
            "improvements": self.improvements,
            "note": self.note,
        }


# ---------------------------------------------------------------------------
# Question generation
# ---------------------------------------------------------------------------

_N_BEHAVIORAL = 3
_N_TECHNICAL = 3
_N_ROLE_SPECIFIC = 2
_N_JD_SKILL = 4  # max skill-specific questions


def generate_questions(
    role_target: str,
    jd_text: str | None = None,
    resume_text: str | None = None,
) -> list[Question]:
    """Generate a tailored list of interview questions.

    Parameters
    ----------
    role_target:
        The role the user is practising for (e.g., "Senior Python Developer").
    jd_text:
        Full text of the job description (optional).  Used to extract
        skill-gap questions and prioritise missing skills.
    resume_text:
        Full text of the resume (optional).  Used to identify gaps when
        combined with jd_text.

    Returns
    -------
    list[Question]
        A deterministic list of questions ordered:
        behavioral → technical → role_specific → jd_skill.
    """
    role_lower = role_target.lower()
    questions: list[Question] = []

    # --- Behavioral (always included) ---
    questions.extend(_pick_behavioral(role_lower))

    # --- Technical (always included) ---
    questions.extend(_pick_technical(role_lower))

    # --- Role-specific ---
    questions.extend(_pick_role_specific(role_lower))

    # --- JD-skill questions (when a JD is available) ---
    if jd_text:
        questions.extend(_pick_jd_skill_questions(jd_text, resume_text))

    return questions


def _pick_behavioral(role_lower: str) -> list[Question]:
    """Select behavioral questions — deterministic slice."""
    selected = _BEHAVIORAL_QUESTIONS[:_N_BEHAVIORAL]
    return [
        Question(text=q, category="behavioral", expected_keywords=kw)
        for q, kw in selected
    ]


def _pick_technical(role_lower: str) -> list[Question]:
    """Select generic technical questions — deterministic slice."""
    selected = _TECHNICAL_QUESTIONS[:_N_TECHNICAL]
    return [
        Question(text=q, category="technical", expected_keywords=kw)
        for q, kw in selected
    ]


def _pick_role_specific(role_lower: str) -> list[Question]:
    """Select role-specific questions by matching role keywords."""
    collected: list[tuple[str, list[str]]] = []
    for keyword, qs in _ROLE_QUESTIONS.items():
        if keyword in role_lower:
            collected.extend(qs)
    # Deduplicate by question text (order-preserving)
    seen: set[str] = set()
    unique: list[tuple[str, list[str]]] = []
    for q, kw in collected:
        if q not in seen:
            seen.add(q)
            unique.append((q, kw))

    selected = unique[:_N_ROLE_SPECIFIC]
    return [
        Question(text=q, category="role_specific", expected_keywords=kw)
        for q, kw in selected
    ]


def _pick_jd_skill_questions(
    jd_text: str,
    resume_text: str | None,
) -> list[Question]:
    """Generate one question per missing (or all) JD skill."""
    jd_skills = _extract_skills(jd_text)
    if not jd_skills:
        return []

    if resume_text:
        resume_skills = _extract_skills(resume_text)
        # Prioritise missing skills; fall back to all JD skills if none missing
        missing = sorted(jd_skills - resume_skills)
        target_skills = missing if missing else sorted(jd_skills)
    else:
        target_skills = sorted(jd_skills)

    selected_skills = target_skills[:_N_JD_SKILL]
    return [
        Question(
            text=_SKILL_QUESTION_TEMPLATE.format(skill=skill),
            category="jd_skill",
            expected_keywords=[skill, "project", "used", "outcome", "result", "built"],
            skill_ref=skill,
        )
        for skill in selected_skills
    ]


# ---------------------------------------------------------------------------
# Answer evaluation
# ---------------------------------------------------------------------------

_STAR_MARKERS = ["situation", "task", "action", "result", "outcome", "i "]
_MIN_WORD_COUNT = 30
_GOOD_WORD_COUNT = 80


def evaluate_answer(question: Question, answer_text: str) -> EvaluationResult:
    """Evaluate a user's answer to an interview question.

    The evaluation is entirely offline and keyword/heuristic-based.
    It produces a 0–100 score along with concrete strengths and
    improvement suggestions.

    Parameters
    ----------
    question:
        The Question the user is answering.
    answer_text:
        The raw text of the user's answer.

    Returns
    -------
    EvaluationResult
    """
    answer_lower = answer_text.lower().strip()
    words = answer_lower.split()
    word_count = len(words)

    # --- 1. Keyword coverage score (0–100) ---
    if question.expected_keywords:
        matched_kw = [
            kw for kw in question.expected_keywords
            if re.search(r"\b" + re.escape(kw) + r"\b", answer_lower)
        ]
        kw_score = len(matched_kw) / len(question.expected_keywords) * 100
    else:
        matched_kw = []
        kw_score = 50.0  # neutral when no keywords available

    # --- 2. Length score (0–100) ---
    if word_count == 0:
        length_score = 0.0
    elif word_count < _MIN_WORD_COUNT:
        length_score = (word_count / _MIN_WORD_COUNT) * 50
    elif word_count < _GOOD_WORD_COUNT:
        length_score = 50 + (word_count - _MIN_WORD_COUNT) / (_GOOD_WORD_COUNT - _MIN_WORD_COUNT) * 50
    else:
        length_score = 100.0

    # --- 3. Structure score — STAR markers for behavioral, basic for others ---
    if question.category == "behavioral":
        star_found = [m for m in _STAR_MARKERS if m in answer_lower]
        structure_score = min(len(star_found) / 3 * 100, 100.0)
    else:
        # For non-behavioral: reward use of specific examples ("for example", "I")
        example_markers = ["for example", "for instance", "in my", "i built", "i used", "i worked"]
        example_found = [m for m in example_markers if m in answer_lower]
        structure_score = min(len(example_found) / 2 * 100, 100.0)

    # --- Composite score ---
    raw_score = kw_score * 0.5 + length_score * 0.25 + structure_score * 0.25
    score = round(min(max(raw_score, 0.0), 100.0), 1)

    # --- Strengths ---
    strengths: list[str] = []
    if word_count >= _GOOD_WORD_COUNT:
        strengths.append("Your answer is detailed and well-developed.")
    elif word_count >= _MIN_WORD_COUNT:
        strengths.append("Your answer covers the basic points.")

    if matched_kw:
        strengths.append(
            f"You addressed relevant concepts: {', '.join(matched_kw[:4])}."
        )

    if question.category == "behavioral" and len([m for m in _STAR_MARKERS[:4] if m in answer_lower]) >= 2:
        strengths.append("Your answer shows signs of a structured (STAR-style) response.")

    if not strengths:
        strengths.append("You attempted to answer the question.")

    # --- Improvements ---
    improvements: list[str] = []
    if word_count < _MIN_WORD_COUNT:
        improvements.append(
            f"Expand your answer — it currently has about {word_count} words. "
            f"Aim for at least {_MIN_WORD_COUNT} words to demonstrate depth."
        )

    missing_kw = [
        kw for kw in question.expected_keywords
        if kw not in matched_kw
    ]
    if missing_kw:
        improvements.append(
            f"Consider addressing: {', '.join(missing_kw[:4])}."
        )

    if question.category == "behavioral":
        star_found = [m for m in _STAR_MARKERS[:4] if m in answer_lower]
        if len(star_found) < 2:
            improvements.append(
                "Structure your answer using the STAR method: describe the Situation, "
                "the Task, the Action you took, and the Result."
            )

    if not improvements:
        improvements.append(
            "Good answer overall. You could strengthen it further by adding a "
            "specific metric or outcome (e.g., 'reduced load time by 30%')."
        )

    note = (
        "This feedback is generated by keyword matching and heuristic rules — "
        "not by an AI language model. The score reflects the presence of relevant "
        "terms and basic structural patterns, not the actual quality of your answer."
    )

    return EvaluationResult(
        score=score,
        strengths=strengths,
        improvements=improvements,
        note=note,
    )
