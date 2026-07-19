"""M7 — monthly checkup: staleness report + version-stamped profile diffs."""

import json
from datetime import date
from pathlib import Path

import pytest

from forge.checkup import (
    STALE_DAYS,
    apply_update,
    checkup_status,
    next_version,
    propose_update,
)


@pytest.fixture
def profile_dir(tmp_path) -> Path:
    d = tmp_path / "profiles"
    d.mkdir()
    (d / "perplexity.json").write_text(json.dumps({
        "engine": "perplexity",
        "version": "2026.07.0",
        "default_mode": "deep-research",
        "structure": "concise-query",
        "length": "concise",
        "source_filter_syntax": ["site:"],
        "strengths": ["s"],
        "directives": ["d"],
        "notes": "n",
        "doc_sources": ["https://docs.perplexity.ai"],
        "last_checked": "2026-07-01",
    }))
    (d / "chatgpt.json").write_text(json.dumps({
        "engine": "chatgpt",
        "version": "2026.05.2",
        "default_mode": "deep-research",
        "structure": "role-framed",
        "length": "long",
        "source_filter_syntax": [],
        "strengths": ["s"],
        "directives": ["d"],
        "notes": "n",
        "doc_sources": ["https://platform.openai.com/docs"],
        "last_checked": "2026-05-15",
    }))
    return d


class TestStatus:
    def test_fresh_and_stale_split(self, profile_dir):
        statuses = checkup_status(now=date(2026, 7, 19), profile_dir=profile_dir)
        by_engine = {s.engine: s for s in statuses}
        assert not by_engine["perplexity"].stale  # 18 days
        assert by_engine["chatgpt"].stale  # 65 days > STALE_DAYS
        assert by_engine["chatgpt"].days_since == 65
        assert STALE_DAYS == 30

    def test_status_carries_doc_sources(self, profile_dir):
        statuses = checkup_status(now=date(2026, 7, 19), profile_dir=profile_dir)
        by_engine = {s.engine: s for s in statuses}
        assert by_engine["perplexity"].doc_sources == ["https://docs.perplexity.ai"]

    def test_missing_last_checked_is_stale(self, profile_dir):
        data = json.loads((profile_dir / "chatgpt.json").read_text())
        del data["last_checked"]
        (profile_dir / "chatgpt.json").write_text(json.dumps(data))
        statuses = checkup_status(now=date(2026, 7, 19), profile_dir=profile_dir)
        by_engine = {s.engine: s for s in statuses}
        assert by_engine["chatgpt"].stale
        assert by_engine["chatgpt"].days_since is None


class TestNextVersion:
    def test_same_month_increments(self):
        assert next_version("2026.07.0", date(2026, 7, 19)) == "2026.07.1"

    def test_new_month_resets(self):
        assert next_version("2026.05.2", date(2026, 7, 19)) == "2026.07.0"


class TestProposeAndApply:
    def test_proposal_is_version_stamped_diff(self, profile_dir):
        proposal = propose_update(
            "perplexity",
            {"length": "very concise", "notes": "updated per docs"},
            now=date(2026, 7, 19),
            profile_dir=profile_dir,
        )
        assert proposal.engine == "perplexity"
        assert proposal.old_version == "2026.07.0"
        assert proposal.new_version == "2026.07.1"
        assert proposal.changes["length"] == ("concise", "very concise")
        # propose never writes
        on_disk = json.loads((profile_dir / "perplexity.json").read_text())
        assert on_disk["version"] == "2026.07.0"

    def test_propose_rejects_unknown_field(self, profile_dir):
        with pytest.raises(ValueError, match="unknown"):
            propose_update("perplexity", {"bogus": 1},
                           now=date(2026, 7, 19), profile_dir=profile_dir)

    def test_propose_rejects_protected_fields(self, profile_dir):
        for field in ("engine", "version", "last_checked"):
            with pytest.raises(ValueError):
                propose_update("perplexity", {field: "x"},
                               now=date(2026, 7, 19), profile_dir=profile_dir)

    def test_propose_rejects_noop_change(self, profile_dir):
        with pytest.raises(ValueError, match="no changes"):
            propose_update("perplexity", {"length": "concise"},
                           now=date(2026, 7, 19), profile_dir=profile_dir)

    def test_apply_writes_stamped_profile(self, profile_dir):
        proposal = propose_update(
            "perplexity", {"length": "very concise"},
            now=date(2026, 7, 19), profile_dir=profile_dir,
        )
        apply_update(proposal, profile_dir=profile_dir)
        data = json.loads((profile_dir / "perplexity.json").read_text())
        assert data["version"] == "2026.07.1"
        assert data["length"] == "very concise"
        assert data["last_checked"] == "2026-07-19"
        assert data["engine"] == "perplexity"  # untouched


class TestShippedProfiles:
    def test_all_four_profiles_have_checkup_fields(self):
        from forge.profile import ENGINES, _PROFILE_DIR

        for engine in ENGINES:
            data = json.loads((_PROFILE_DIR / f"{engine}.json").read_text())
            assert data.get("doc_sources"), f"{engine} missing doc_sources"
            assert data.get("last_checked"), f"{engine} missing last_checked"
