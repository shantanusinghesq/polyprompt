"""M4 — advisory validation: expected tactics vs applied, never blocking."""

from forge.__main__ import main
from forge.graph import Graph, load_graph, save_graph, seed_graph
from forge.taxonomy import load_taxonomy
from forge.validate import validate


def promoted_graph(tactic="concise-query", dimension="engine", value="chatgpt"):
    graph = Graph(taxonomy_version="v1")
    for _ in range(10):
        graph.add_label(tactic, dimension, value)
    return graph


class TestValidate:
    def test_missing_required_tactic_is_flagged(self):
        graph = promoted_graph()
        flags = validate(
            applied_tactics=["role-framing"], tags={"engine": "chatgpt"}, graph=graph
        )
        assert len(flags) == 1
        flag = flags[0]
        assert flag.tactic == "concise-query"
        assert flag.dimension == "engine"
        assert flag.value == "chatgpt"
        assert flag.severity == "advisory"
        assert flag.support >= 10
        assert flag.weight >= 0.7

    def test_applied_required_tactic_not_flagged(self):
        graph = promoted_graph()
        flags = validate(
            applied_tactics=["concise-query"], tags={"engine": "chatgpt"}, graph=graph
        )
        assert flags == []

    def test_below_gate_edges_do_not_flag(self):
        graph = Graph(taxonomy_version="v1")
        for _ in range(4):
            graph.add_label("concise-query", "engine", "chatgpt")
        assert validate([], {"engine": "chatgpt"}, graph) == []

    def test_seed_only_graph_never_flags(self):
        graph = seed_graph(load_taxonomy())
        tags = {
            "engine": "perplexity",
            "mode": "deep-research",
            "method": "mixed",
            "analysis_type": "descriptive",
            "retrieval_type": "synthesis",
            "subject_matter": "general",
        }
        assert validate([], tags, graph) == []

    def test_unrelated_tags_do_not_flag(self):
        graph = promoted_graph()
        assert validate([], {"engine": "gemini"}, graph) == []


class TestCliIntegration:
    def test_rewrite_with_graph_creates_seeded_graph_file(self, tmp_path, capsys):
        graph_path = tmp_path / "graph.json"
        rc = main(
            [
                "rewrite",
                "Compare heat pump and furnace costs",
                "--engine",
                "chatgpt",
                "--graph",
                str(graph_path),
            ]
        )
        assert rc == 0
        assert graph_path.exists()
        loaded = load_graph(graph_path)
        assert len(loaded.edges) > 0

    def test_validation_flags_are_advisory_not_blocking(self, tmp_path, capsys):
        # concise-query promoted for engine=chatgpt, which the chatgpt
        # renderer never applies -> must flag, must still exit 0.
        graph_path = tmp_path / "graph.json"
        save_graph(promoted_graph(), graph_path)
        rc = main(
            [
                "rewrite",
                "Compare heat pump and furnace costs",
                "--engine",
                "chatgpt",
                "--graph",
                str(graph_path),
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out.lower()
        assert "advisory" in out
        assert "concise-query" in out

    def test_memos_are_ingested_into_graph(self, tmp_path):
        graph_path = tmp_path / "graph.json"
        rc = main(
            [
                "rewrite",
                "Compare heat pump and furnace costs",
                "--engine",
                "all",
                "--memos",
                str(tmp_path / "memos"),
                "--graph",
                str(graph_path),
            ]
        )
        assert rc == 0
        loaded = load_graph(graph_path)
        # one memo per engine ingested
        assert len(loaded.ingested) == 4
