"""M8 — the Perplexity renderer targets the retrieval stage, not just phrasing.

A RAG engine embeds and keyword-matches the query *before* any generation, so
the query string decides which documents the model ever sees. These tests pin
the three properties that follow from that, plus the two provenance defects
found when the renderer was reworked.
"""

from polyprompt.graph import seed_graph
from polyprompt.intake import IntakeAnswers
from polyprompt.ir import normalize
from polyprompt.profile import load_all_profiles, load_profile
from polyprompt.rewrite import rewrite
from polyprompt.taxonomy import load_taxonomy
from polyprompt.validate import validate

PREMISE_PROMPT = (
    "OpenAI, Claude, Gemini all reported AI agents had broken out of AI sandbox "
    "environments during an exercise in which third parties experienced intrusion. "
    "Across all three frontier model developers, what was the root cause after an "
    "investigation, and what did they do to discover and contain the breakout."
)
CLARIFY = (
    "Verify the premise before answering: establish whether each named provider "
    "actually published such a self-disclosure, with document, date and URL."
)


def _perplexity(prompt=PREMISE_PROMPT, **intake):
    ir = normalize(prompt, IntakeAnswers(**intake))
    return ir, rewrite(ir, load_profile("perplexity"))


class TestEntityExtraction:
    def test_product_names_resolve_to_canonical_orgs(self):
        ir, _ = normalize(PREMISE_PROMPT), None
        assert ir.entities == ["OpenAI", "Anthropic", "Google DeepMind"]

    def test_entities_are_deduped(self):
        ir = normalize("Compare OpenAI and ChatGPT and GPT behaviour")
        assert ir.entities == ["OpenAI"]

    def test_no_orgs_means_no_entities(self):
        assert normalize("Compare heat pumps vs gas furnaces").entities == []


class TestPremiseDemotion:
    def test_assertion_is_not_in_the_retrieval_lead(self):
        _, result = _perplexity()
        lead = result.prompt.splitlines()[0]
        # the lead drives nearest-neighbour retrieval; keying it on the
        # assertion returns documents lexically near the claim, not evidence
        assert "reported" not in lead
        assert "experienced intrusion" not in lead

    def test_assertion_is_preserved_as_a_claim_to_verify(self):
        _, result = _perplexity()
        assert "Claim to verify, do not assume true:" in result.prompt
        assert "premise-demotion" in result.tactics

    def test_questions_survive_into_the_lead(self):
        _, result = _perplexity()
        lead = result.prompt.splitlines()[0].lower()
        for term in ("root", "cause", "contain", "breakout"):
            assert term in lead

    def test_all_declarative_prompt_demotes_nothing(self):
        # no ask-marker: fall back to the whole prompt as the lead
        _, result = _perplexity("Root causes of sandbox escapes in agent systems.")
        assert "Claim to verify" not in result.prompt
        assert "premise-demotion" not in result.tactics


class TestEntitySiteScoping:
    def test_named_orgs_become_site_operators(self):
        _, result = _perplexity()
        assert "site:openai.com" in result.prompt
        assert "site:anthropic.com" in result.prompt
        assert "site:deepmind.google" in result.prompt
        assert "entity-site-scoping" in result.tactics

    def test_no_entities_means_no_site_operators(self):
        _, result = _perplexity("Compare heat pumps vs gas furnaces")
        assert "site:" not in result.prompt
        assert "entity-site-scoping" not in result.tactics

    def test_site_map_is_profile_config_not_hardcoded(self):
        profile = load_profile("perplexity")
        assert profile.site_map["Anthropic"] == ["anthropic.com"]
        # other engines carry no map and must not emit site:
        assert load_profile("chatgpt").site_map == {}


class TestDecomposition:
    def test_multiple_entities_request_separate_searches(self):
        _, result = _perplexity()
        assert "Search each separately:" in result.prompt
        assert "decomposition" in result.tactics

    def test_single_entity_does_not_decompose(self):
        _, result = _perplexity("What did OpenAI disclose about agent sandboxing?")
        assert "decomposition" not in result.tactics


class TestConstraintsAreRendered:
    """The original defect: the renderer never read ir.constraints, yet the
    uniform post-step still reported `disambiguation` as applied."""

    def test_clarification_reaches_the_query(self):
        _, result = _perplexity(clarifications=CLARIFY)
        assert "Verify the premise before answering" in result.prompt
        assert "disambiguation" in result.tactics

    def test_disambiguation_not_claimed_without_constraints(self):
        _, result = _perplexity()
        assert "disambiguation" not in result.tactics


class TestProvenanceValidation:
    """Over-claiming check: a tactic ID with no trace in the rendered text."""

    def _graph(self):
        return seed_graph(load_taxonomy())

    def test_overclaimed_tactic_is_flagged(self):
        # the pre-fix output: disambiguation claimed, clause absent
        text = "Some query. Prefer primary sources. after:2023. Cite sources."
        flags = validate(
            ["concise-query", "disambiguation"],
            {"engine": "perplexity"},
            self._graph(),
            text,
            [CLARIFY],
        )
        assert [f.tactic for f in flags if f.severity == "provenance"] == [
            "disambiguation"
        ]

    def test_content_check_is_label_agnostic(self):
        # Gemini renders constraints under "Scope:", not "Constraints:" —
        # probing for the label instead of the content false-positived here
        gemini = rewrite(
            normalize(PREMISE_PROMPT, IntakeAnswers(clarifications=CLARIFY)),
            load_profile("gemini"),
        )
        flags = validate(
            gemini.tactics, {"engine": "gemini"}, self._graph(), gemini.prompt, [CLARIFY]
        )
        assert [f for f in flags if f.severity == "provenance"] == []

    def test_no_provenance_flags_on_any_current_renderer(self):
        ir = normalize(PREMISE_PROMPT, IntakeAnswers(time_period="2024+", depth=3,
                                                     clarifications=CLARIFY))
        graph = self._graph()
        for engine, profile in load_all_profiles().items():
            result = rewrite(ir, profile)
            flags = validate(
                result.tactics, {"engine": engine}, graph, result.prompt, ir.constraints
            )
            assert [f.tactic for f in flags if f.severity == "provenance"] == [], engine

    def test_provenance_check_is_skipped_without_the_prompt(self):
        # back-compat: the 3-arg call site must behave as before
        assert validate(["disambiguation"], {"engine": "perplexity"}, self._graph()) == []


class TestConcisenessPreserved:
    def test_perplexity_stays_shortest_for_a_plain_prompt(self):
        ir = normalize(
            "Compare 15-year TCO of heat pumps vs gas furnaces",
            IntakeAnswers(time_period="2024+", depth=3),
        )
        profiles = load_all_profiles()
        ppx = len(rewrite(ir, profiles["perplexity"]).prompt)
        for other in ("chatgpt", "gemini", "claude"):
            assert ppx <= len(rewrite(ir, profiles[other]).prompt)

    def test_retrieval_lead_is_bounded(self):
        _, result = _perplexity(clarifications=CLARIFY)
        assert len(result.prompt.splitlines()[0]) < 400


class TestAskDetection:
    """A marker after a preposition relativises; it does not ask."""

    def test_relative_clause_is_not_an_ask(self):
        from polyprompt.rewrite import _is_ask

        assert not _is_ask("An exercise in which third parties were breached.")
        assert not _is_ask("The basis on which the agents were sandboxed.")

    def test_genuine_question_is_an_ask(self):
        from polyprompt.rewrite import _is_ask

        assert _is_ask("Which providers published a disclosure?")
        assert _is_ask("What was the root cause?")

    def test_relativiser_only_premise_is_demoted(self):
        ir = normalize(
            "Agents escaped during an exercise in which third parties were breached. "
            "What was the root cause?"
        )
        result = rewrite(ir, load_profile("perplexity"))
        assert "Claim to verify" in result.prompt
        assert "in which third parties" not in result.prompt.splitlines()[0]
