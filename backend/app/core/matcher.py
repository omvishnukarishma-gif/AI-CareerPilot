"""Deterministic resume–job-description matcher.

Algorithm overview
------------------
This module provides an offline, dependency-free matching algorithm that
does NOT require any AI API keys or network access.  It is intentionally
transparent and auditable so users can understand exactly why they received
a given score.

Scoring method
~~~~~~~~~~~~~~
1. **Skill extraction** — a curated vocabulary of ~250 technology and
   professional skills (keywords / short phrases) is matched against the
   raw text of both the resume and the job description using whole-word,
   case-insensitive search.  Compound phrases (e.g. "machine learning") are
   matched before single words to avoid partial matches.

2. **Match score** — computed as:

       score = (matched_count / max(jd_skill_count, 1)) * 100

   capped at 100.  A job description that mentions N skills and the resume
   covers M of them earns (M/N)×100.  If the JD mentions no known skills the
   score is 0.

3. **Matched skills** — skills that appear in BOTH texts.
4. **Missing skills** — skills that appear in the JD but NOT in the resume.
5. **Recommendations** — one honest sentence per missing skill explaining
   that the skill was not found in the resume (not that the candidate lacks
   the skill), plus a general note about the method's limitations.

Limitations
~~~~~~~~~~~
- Keyword matching cannot understand context: a resume mentioning "Python"
  in "I tutored Python beginners" will score the same as one demonstrating
  deep Python expertise.
- Synonyms are not resolved (e.g. "JS" vs "JavaScript").  The vocabulary
  includes the most common aliases but is not exhaustive.
- Skills not in the vocabulary are silently ignored.
- The score is a rough heuristic, not a hiring recommendation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Skill vocabulary
# ---------------------------------------------------------------------------
# Organised roughly by category for maintainability.
# Longer / more-specific phrases appear before shorter ones so they are
# matched first in the extraction loop.

_SKILL_VOCABULARY: list[str] = [
    # ── Programming languages ──────────────────────────────────────────────
    "python", "javascript", "typescript", "java", "kotlin", "swift",
    "c++", "c#", "go", "rust", "ruby", "php", "scala", "r",
    "bash", "shell scripting", "powershell", "perl", "lua",
    # ── Web / frontend ────────────────────────────────────────────────────
    "react", "react native", "vue", "vue.js", "angular", "svelte",
    "next.js", "nuxt", "remix", "html", "css", "sass", "tailwind css",
    "tailwind", "bootstrap", "webpack", "vite", "rollup", "parcel",
    "graphql", "rest api", "restful api", "rest", "websockets",
    # ── Backend / server ──────────────────────────────────────────────────
    "fastapi", "django", "flask", "express", "node.js", "nodejs",
    "spring boot", "spring", "rails", "laravel", "nestjs",
    "grpc", "microservices", "serverless",
    # ── Databases ─────────────────────────────────────────────────────────
    "postgresql", "mysql", "sqlite", "oracle", "sql server",
    "mongodb", "redis", "elasticsearch", "cassandra", "dynamodb",
    "sql", "nosql", "orm", "sqlalchemy", "prisma",
    # ── Cloud & infrastructure ────────────────────────────────────────────
    "aws", "azure", "google cloud", "gcp", "heroku", "vercel",
    "docker", "kubernetes", "terraform", "ansible", "helm",
    "ci/cd", "github actions", "gitlab ci", "jenkins", "circleci",
    "nginx", "apache", "load balancing", "cdn",
    # ── Data / ML / AI ────────────────────────────────────────────────────
    "machine learning", "deep learning", "natural language processing",
    "nlp", "computer vision", "pytorch", "tensorflow", "keras",
    "scikit-learn", "pandas", "numpy", "matplotlib", "seaborn",
    "data analysis", "data engineering", "data science",
    "apache spark", "kafka", "airflow", "dbt", "etl",
    "llm", "openai", "langchain", "hugging face",
    # ── Testing ───────────────────────────────────────────────────────────
    "unit testing", "integration testing", "end-to-end testing",
    "tdd", "bdd", "pytest", "jest", "vitest", "cypress", "selenium",
    "playwright", "test driven development",
    # ── Version control & collaboration ───────────────────────────────────
    "git", "github", "gitlab", "bitbucket", "code review",
    "pull request", "agile", "scrum", "kanban", "jira", "confluence",
    # ── Security ──────────────────────────────────────────────────────────
    "oauth", "jwt", "authentication", "authorization", "ssl", "tls",
    "penetration testing", "owasp", "vulnerability assessment",
    # ── Mobile ────────────────────────────────────────────────────────────
    "ios", "android", "flutter", "react native",
    # ── Soft / general professional skills ────────────────────────────────
    "communication", "leadership", "mentoring", "project management",
    "problem solving", "team collaboration", "documentation",
    "technical writing", "code review",
    # ── Databases / query languages ───────────────────────────────────────
    "elasticsearch", "redis", "memcached",
    # ── Architecture & design ─────────────────────────────────────────────
    "system design", "api design", "design patterns",
    "domain-driven design", "event-driven architecture",
    "object-oriented programming", "functional programming",
    "oop", "solid principles",
    # ── DevOps / SRE ──────────────────────────────────────────────────────
    "monitoring", "logging", "observability", "prometheus", "grafana",
    "datadog", "new relic", "pagerduty",
    # ── Misc tools ────────────────────────────────────────────────────────
    "linux", "unix", "macos", "windows server",
    "excel", "tableau", "power bi",
    "figma", "sketch",
]

# De-duplicate while preserving order (longest first to match phrases before
# their sub-words).
_seen: set[str] = set()
SKILLS: list[str] = []
for _s in sorted(_SKILL_VOCABULARY, key=len, reverse=True):
    if _s not in _seen:
        _seen.add(_s)
        SKILLS.append(_s)


# ---------------------------------------------------------------------------
# Core extraction helper
# ---------------------------------------------------------------------------

def _extract_skills(text: str) -> set[str]:
    """Return the set of vocabulary skills found in *text*.

    Uses whole-word, case-insensitive regex matching.  Compound phrases
    (e.g. "machine learning") are attempted before their constituent words
    because SKILLS is sorted longest-first.
    """
    normalised = text.lower()
    found: set[str] = set()

    for skill in SKILLS:
        # Escape special regex chars in the skill phrase, then wrap in word
        # boundaries.  Use \\b only on the boundary chars that are word chars
        # (\w); for phrases ending in punctuation (e.g. "c++", "c#", "node.js")
        # use a lookahead/lookbehind for non-word characters.
        pattern = re.compile(
            r"(?<![a-z0-9._#+-])" + re.escape(skill) + r"(?![a-z0-9._#+-])",
            re.IGNORECASE,
        )
        if pattern.search(normalised):
            found.add(skill)

    return found


# ---------------------------------------------------------------------------
# Public dataclass for match results
# ---------------------------------------------------------------------------

@dataclass
class MatchResult:
    """The output of a single resume–JD comparison.

    Attributes
    ----------
    score:
        0–100 float representing the fraction of JD skills found in the resume.
    matched_skills:
        Sorted list of skills present in both resume and JD.
    missing_skills:
        Sorted list of skills required by the JD but absent from the resume.
    recommendations:
        Actionable, honest suggestions addressing the missing skills.
    """

    score: float
    matched_skills: list[str]
    missing_skills: list[str]
    recommendations: list[str]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_match(resume_text: str, jd_text: str) -> MatchResult:
    """Compare *resume_text* against *jd_text* and return a MatchResult.

    Parameters
    ----------
    resume_text:
        The full plain-text content of the resume (extracted by the
        app.core.extractor module).
    jd_text:
        The full text of the job description as pasted by the user.

    Returns
    -------
    MatchResult
        Contains a 0–100 score, matched skills, missing skills, and
        one recommendation per missing skill.
    """
    jd_skills = _extract_skills(jd_text)
    resume_skills = _extract_skills(resume_text)

    matched = sorted(jd_skills & resume_skills)
    missing = sorted(jd_skills - resume_skills)

    # Score: fraction of JD skills covered by the resume, scaled to 0–100.
    if jd_skills:
        raw_score = len(matched) / len(jd_skills) * 100.0
        score = round(min(raw_score, 100.0), 1)
    else:
        # If the JD has no recognised skills the comparison is inconclusive.
        score = 0.0

    recommendations = _build_recommendations(missing, score)

    return MatchResult(
        score=score,
        matched_skills=matched,
        missing_skills=missing,
        recommendations=recommendations,
    )


def _build_recommendations(missing_skills: list[str], score: float) -> list[str]:
    """Generate honest, actionable recommendations for each missing skill.

    Important: recommendations say "not found in your resume" rather than
    "you lack this skill" — a skill's absence from a document does not imply
    the candidate does not possess it.
    """
    recs: list[str] = []

    if not missing_skills:
        recs.append(
            "Great match! All skills identified in the job description were "
            "found in your resume. Consider reviewing the full job posting for "
            "any requirements this analysis may have missed."
        )
        return recs

    # Per-skill recommendations
    for skill in missing_skills:
        recs.append(
            f'"{skill.title()}" was not found in your resume. '
            f"If you have experience with {skill}, consider adding it explicitly. "
            f"If you are new to {skill}, it may be worth exploring online resources or projects to build familiarity."
        )

    # General caveat — always appended so users understand the method
    recs.append(
        "Note: this analysis uses keyword matching against a fixed vocabulary "
        "and cannot assess the depth of your experience or skills described in "
        "different terms. Review the full job description to ensure you address "
        "all requirements in your application."
    )

    return recs
