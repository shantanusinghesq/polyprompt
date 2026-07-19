"""Sufficiency gate CLI — `forge sufficiency` exit codes + push advisory."""

from forge.__main__ import main
from forge.graph import Graph, save_graph
from tests.test_m5_cli import patch_runner
from tests.test_m5_push import fresh_repo_runner
from tests.test_sufficiency import fm_for_edge, write_memos


class TestSufficiencyCli:
    def test_insufficient_exits_one(self, tmp_path, capsys):
        memos = tmp_path / "memos"
        memos.mkdir()
        rc = main(["sufficiency", "--memos", str(memos),
                   "--graph", str(tmp_path / "g.json")])
        assert rc == 1
        assert "insufficient" in capsys.readouterr().out.lower()

    def test_sufficient_exits_zero_with_triage(self, tmp_path, capsys):
        graph = Graph(taxonomy_version="v1")
        for _ in range(7):
            graph.add_label("role-framing", "engine", "chatgpt")
        graph_path = tmp_path / "g.json"
        save_graph(graph, graph_path)
        memos = write_memos(tmp_path / "memos",
                            [fm_for_edge(f"hash{i:02d}") for i in range(3)])
        rc = main(["sufficiency", "--memos", str(memos), "--graph", str(graph_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "PROMOTE-READY" in out
        assert "role-framing" in out

    def test_push_prints_sufficiency_advisory(self, tmp_path, monkeypatch, capsys):
        memos = write_memos(tmp_path / "memos",
                            [fm_for_edge(f"hash{i:02d}") for i in range(3)])
        save_graph(Graph(taxonomy_version="v1"), memos / "graph.json")
        patch_runner(monkeypatch, fresh_repo_runner())
        rc = main(["push", "--dir", str(memos), "--repo", "corpus-repo"])
        assert rc == 0
        assert "sufficiency" in capsys.readouterr().out.lower()
