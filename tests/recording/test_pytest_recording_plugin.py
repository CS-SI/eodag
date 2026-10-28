"""Tests d'intégration pytest de ``eodag.utils.recording.pytest_integration``."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

pytest_plugins = ["pytester"]


def _symlinks_supported() -> bool:
    """False e.g. on Windows without Developer Mode."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.symlink(tmp, os.path.join(tmp, "link"), target_is_directory=True)
        except (OSError, NotImplementedError):
            return False
    return True


requires_symlinks = pytest.mark.skipif(
    not _symlinks_supported(), reason="symbolic links are not available"
)
HERE = Path(__file__).parent

TEST_MODULE = """
import os
import pytest
from eodag.utils.recording.pytest_integration import eodag_record
from fake_provider import make_gateway


def _flow(tmp_path):
    gw = make_gateway(tmp_path / "out")
    res = gw.search(collection="C", start="2024-01-01", limit=2)
    path = gw.download(res[0])
    assert os.path.islink(path)
    assert open(os.path.join(path, "data.txt")).read() == "content of C_p1_0"
    return gw


@eodag_record()
def test_default(tmp_path):
    _flow(tmp_path)


@pytest.mark.eodag_record(record_mode="once")
def test_marker_once(tmp_path):
    _flow(tmp_path)


@pytest.mark.parametrize("coll", ["C", "D"])
@eodag_record(record_mode="once")
def test_param(tmp_path, coll):
    make_gateway(tmp_path).search(collection=coll)


@eodag_record(cassettes=["shared_a", "shared_b"], write_to="shared_b", record_mode="once")
def test_two_cassettes(tmp_path):
    make_gateway(tmp_path).search(collection="C")


@eodag_record(cassettes=lambda request: f"custom_{request.node.name}", record_mode="once")
def test_callable_name(tmp_path):
    make_gateway(tmp_path).search_all(collection="C")


def test_fixture_only(eodag_recorder, tmp_path):
    make_gateway(tmp_path).search(collection="C")
"""

FAILING_MODULE = """
from eodag.utils.recording.pytest_integration import eodag_record
from fake_provider import make_gateway

@eodag_record(record_mode="all")
def test_fails(tmp_path):
    make_gateway(tmp_path).search(collection="C")
    assert False
"""

CONFTEST = """
pytest_plugins = ["eodag.utils.recording.pytest_integration"]
import fake_provider
fake_provider.install()
"""


@pytest.fixture
def project(pytester):
    pytester.makepyfile(fake_provider=(HERE / "fake_provider.py").read_text())
    pytester.makeconftest(CONFTEST)
    pytester.makepyfile(test_mod=TEST_MODULE, test_failing=FAILING_MODULE)
    return pytester


def run(project, *args, forbid=False, select="test_mod.py"):
    import os

    env = dict(os.environ)
    env.pop("FAKE_FORBID", None)
    if forbid:
        env["FAKE_FORBID"] = "1"
    old = os.environ.copy()
    os.environ.clear()
    os.environ.update(env)
    try:
        return project.runpytest_subprocess("-p", "no:cacheprovider", select, *args)
    finally:
        os.environ.clear()
        os.environ.update(old)


def cassettes(project):
    return sorted(
        p.relative_to(project.path / "cassettes").as_posix()
        for p in (project.path / "cassettes").rglob("*.yaml")
    )


@requires_symlinks
def test_record_all_then_replay_none(project):
    # tout réenregistrer (CLI), hors test_fixture_only et test_default qui n'écrivent qu'en all
    result = run(project, "--eodag-record-mode=all")
    result.assert_outcomes(passed=7)
    names = cassettes(project)
    assert "test_mod/test_default.yaml" in names
    assert (
        "test_mod/test_param[C].yaml" in names
        and "test_mod/test_param[D].yaml" in names
    )
    assert "test_mod/test_fixture_only.yaml" in names
    # seule la cassette d'écriture (shared_b) est écrite
    assert "shared_b.yaml" in names and "shared_a.yaml" not in names
    assert "custom_test_callable_name.yaml" in names
    assert (project.path / "cassettes" / "_downloads" / "C_p1_0" / "data.txt").exists()

    # rejeu strict : plus aucun appel réel autorisé
    # (shared_b seule contient la recherche ; shared_a absente est tolérée)
    result = run(project, "--eodag-record-mode=none", forbid=True)
    result.assert_outcomes(passed=7)


@requires_symlinks
def test_once_via_marker_and_default_none(project):
    # Sans CLI : défaut « none » pour test_default / test_fixture_only (échec, cassette
    # absente), mais le marqueur « once » enregistre les 5 autres.
    result = run(project)
    result.assert_outcomes(passed=5, failed=2)
    result.stdout.fnmatch_lines(["*No recording matches*"])
    assert "test_mod/test_marker_once.yaml" in cassettes(project)
    assert "test_mod/test_default.yaml" not in cassettes(project)

    # 2e exécution : les cassettes existent -> rejeu, sans aucun appel réel
    result = run(project, forbid=True)
    result.assert_outcomes(passed=5, failed=2)


@requires_symlinks
def test_cli_overrides_marker(project):
    # le marqueur dit « once » (enregistrerait), la CLI dit « none » et l'emporte
    result = run(project, "--eodag-record-mode=none", "-k", "test_marker_once")
    result.assert_outcomes(failed=1)
    assert "test_mod/test_marker_once.yaml" not in cassettes(project)


def test_no_write_when_test_fails(project):
    result = run(project, select="test_failing.py")
    result.assert_outcomes(failed=1)
    assert cassettes(project) == []


@requires_symlinks
def test_new_episodes_via_cli(project):
    run(project, "--eodag-record-mode=all", "-k", "test_default").assert_outcomes(
        passed=1
    )
    path = project.path / "cassettes" / "test_mod" / "test_default.yaml"
    before = yaml.safe_load(path.read_text())
    assert len(before["search"]) == 1
    # nouveau mode : l'existant est rejoué (FAKE_FORBID n'empêche pas les appels inconnus)
    run(
        project, "--eodag-record-mode=new_episodes", "-k", "test_default"
    ).assert_outcomes(passed=1)
    assert yaml.safe_load(path.read_text()) == before
