"""M7 — `polyprompt checkup` CLI wiring."""

import json

from polyprompt.__main__ import main


class TestCheckupCli:
    def test_report_lists_engines_and_staleness(self, capsys):
        rc = main(["checkup"])
        assert rc == 0
        out = capsys.readouterr().out
        for engine in ("chatgpt", "gemini", "claude", "perplexity"):
            assert engine in out
        assert "doc" in out.lower()  # surfaces the sources to review

    def test_propose_prints_version_stamped_diff(self, tmp_path, capsys, monkeypatch):
        # copy real profiles into a sandbox so --apply never touches the repo
        from polyprompt.profile import _PROFILE_DIR

        sandbox = tmp_path / "profiles"
        sandbox.mkdir()
        for p in _PROFILE_DIR.glob("*.json"):
            (sandbox / p.name).write_text(p.read_text())
        monkeypatch.setenv("FORGE_PROFILE_DIR", str(sandbox))

        rc = main(["checkup", "--engine", "perplexity",
                   "--set", 'length="ultra concise"'])
        assert rc == 0
        out = capsys.readouterr().out
        assert "->" in out and "length" in out
        # proposal only — file unchanged without --apply
        assert json.loads((sandbox / "perplexity.json").read_text())["length"] != "ultra concise"

        rc = main(["checkup", "--engine", "perplexity",
                   "--set", 'length="ultra concise"', "--apply"])
        assert rc == 0
        data = json.loads((sandbox / "perplexity.json").read_text())
        assert data["length"] == "ultra concise"

    def test_bad_set_value_errors(self, capsys):
        rc = main(["checkup", "--engine", "perplexity", "--set", "length=not-json"])
        assert rc == 2
