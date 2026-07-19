"""M0 hardcoded Perplexity transform (walking skeleton).

Perplexity rewards concise, keyword-forward queries that ask for cited, recent,
primary sources. This is a deterministic placeholder — M1 replaces it with a
profile-driven rewrite over the PromptIR.
"""

from __future__ import annotations

_PERPLEXITY_DIRECTIVE = (
    "Focus: concise, source-cited answer. "
    "Prefer primary and recent sources; include citations."
)


def perplexity_transform(prompt: str) -> str:
    """Return a Perplexity-leaning rewrite of a general research prompt.

    Raises:
        ValueError: if the prompt is empty or whitespace-only.
    """
    core = " ".join(prompt.strip().split())
    if not core:
        raise ValueError("prompt must be non-empty")
    return f"{core}\n\n{_PERPLEXITY_DIRECTIVE}"
