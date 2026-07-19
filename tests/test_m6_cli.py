"""M6 — `polyprompt review` CLI wiring (pure file I/O, no subprocesses)."""

from polyprompt.__main__ import main
from polyprompt.graph import load_graph
from polyprompt.memo import render_frontmatter
from tests.test_m4_graph import make_frontmatter


def write_memo(directory, fm=None):
    directory.mkdir(parents=True, exist_ok=True)
    fm = fm or make_frontmatter()
    path = directory / "2026-07-19-x-chatgpt.md"
    path.write_text(render_frontmatter(fm) + "\nbody\n")
    return path


class TestReviewCli:
    def test_review_writes_sidecar_and_updates_graph(self, tmp_path, capsys):
        memo = write_memo(tmp_path / "memos")
        graph_path = tmp_path / "graph.json"
        rc = main(
            [
                "review", str(memo),
                "--reviewer", "alex",
                "--intent", "5",
                "--quality", "5",
                "--explain", "solid layered reasoning",
                "--mode-correct",
                "--graph", str(graph_path),
            ]
        )
        assert rc == 0
        assert (tmp_path / "memos" / "2026-07-19-x-chatgpt.review.json").exists()
        loaded = load_graph(graph_path)
        assert len(loaded.edges) > 0
        out = capsys.readouterr().out.lower()
        assert "positive" in out
        assert "mode accuracy" in out

    def test_duplicate_review_reports_and_exits_zero(self, tmp_path, capsys):
        memo = write_memo(tmp_path / "memos")
        graph_path = tmp_path / "graph.json"
        args = [
            "review", str(memo), "--reviewer", "alex", "--intent", "5",
            "--quality", "5", "--explain", "x", "--mode-correct",
            "--graph", str(graph_path),
        ]
        assert main(args) == 0
        assert main(args) == 0
        assert "already" in capsys.readouterr().out.lower()

    def test_missing_memo_errors(self, tmp_path, capsys):
        rc = main(
            [
                "review", str(tmp_path / "nope.md"), "--reviewer", "alex",
                "--intent", "5", "--quality", "5", "--explain", "x",
                "--mode-correct", "--graph", str(tmp_path / "g.json"),
            ]
        )
        assert rc == 2
