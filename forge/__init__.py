"""Research Prompt Forge — rewrite one general research prompt into per-engine
optimized prompts with explanation memos.

M0 (walking skeleton): a single hardcoded Perplexity transform behind the
`forge rewrite` CLI and the `/forge-prompts` plugin command. Later milestones
grow this into the full intake -> IR -> per-engine rewrite -> memo -> knowledge
graph pipeline described in the PRD.
"""

__version__ = "0.0.1"
