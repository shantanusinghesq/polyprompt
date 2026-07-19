"""M1 — platform profile loading + schema validation."""

import pytest

from forge.profile import ENGINES, load_all_profiles, load_profile


def test_all_profiles_load():
    profiles = load_all_profiles()
    assert set(profiles) == set(ENGINES)


def test_profiles_have_versions_and_hardcoded_mode():
    for engine, profile in load_all_profiles().items():
        assert profile.version, f"{engine} profile missing version"
        assert profile.default_mode == "deep-research"  # M1 hardcoded; M3 overrides
        assert profile.engine == engine


def test_profiles_have_distinct_structures():
    structures = {p.structure for p in load_all_profiles().values()}
    assert len(structures) == 4, "each engine must map to a distinct render structure"


def test_unknown_engine_raises():
    with pytest.raises(ValueError):
        load_profile("bing")
