"""Unit tests of de ``eodag.utils.recording`` (without pytest integration)."""

import os
from pathlib import Path

import pytest
import yaml
from shapely import wkt

from eodag.utils.exceptions import NotAvailableError, RequestError, TimeOutError
from eodag.utils.recording import (
    DuplicateKeyError,
    EodagRecorder,
    EodagRecordingConfigError,
    EodagRecordingError,
    EodagRecordingWarning,
    NoMatchingRecordError,
)
from eodag.utils.recording.cassette import Cassette
from tests.recording import fake_provider as fake


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    monkeypatch.delenv("FAKE_FORBID", raising=False)
    fake.install(monkeypatch)


@pytest.fixture
def cassette(tmp_path):
    return tmp_path / "c.yaml"


@pytest.fixture
def gateway(tmp_path):
    return fake.make_gateway(tmp_path / "default_out")


def recorder(mode, cassette, tmp_path, **kw):
    return EodagRecorder(
        mode, kw.pop("cassettes", [cassette]), tmp_path / "archive", **kw
    )


def record(mode, cassette, tmp_path, fn, save=True, **kw):
    rec = recorder(mode, cassette, tmp_path, **kw)
    with rec.patched():
        out = fn()
    rec.finalize(save)
    return out


def replay(cassette, tmp_path, fn, mode="none", **kw):
    rec = recorder(mode, cassette, tmp_path, **kw)
    with rec.patched():
        return fn()


# ------------------------------------------------------------------ search --
def test_search_roundtrip(gateway, cassette, tmp_path):
    def call():
        return gateway.search(collection="C", start="2024-01-01", limit=2, count=True)

    real = record("all", cassette, tmp_path, call)
    assert len(fake.CALLS["search"]) == 1

    os.environ["FAKE_FORBID"] = "1"
    try:
        replayed = replay(cassette, tmp_path, call)
    finally:
        del os.environ["FAKE_FORBID"]

    assert len(replayed) == len(real) == 3
    assert replayed.number_matched == 6
    for a, b in zip(real, replayed):
        assert a.properties["id"] == b.properties["id"]
        assert a.provider == b.provider == "fake_provider"
        assert a.collection == b.collection == "C"
        assert a.geometry.equals(b.geometry)
        assert b.search_intersection.equals(wkt.loads(fake.INTERSECTION))
        assert "eodag:download_link" not in b.properties
        assert b.properties["nested"] == a.properties["nested"]
        assert b.properties["datetime"] == "2024-01-01T00:00:00Z"


def test_search_strict_matching(gateway, cassette, tmp_path):
    record("all", cassette, tmp_path, lambda: gateway.search(collection="C", limit=2))
    # defaults not applied : page=1 explicit = other request
    with pytest.raises(NoMatchingRecordError) as err:
        replay(
            cassette, tmp_path, lambda: gateway.search(collection="C", limit=2, page=1)
        )
    msg = str(err.value)
    assert "page" in msg and "not in recording" in msg
    # modified parameter
    with pytest.raises(NoMatchingRecordError, match="limit"):
        replay(cassette, tmp_path, lambda: gateway.search(collection="C", limit=3))


def test_positional_equals_keyword(gateway, cassette, tmp_path):
    record("all", cassette, tmp_path, lambda: gateway.search(2, collection="C"))
    res = replay(cassette, tmp_path, lambda: gateway.search(page=2, collection="C"))
    assert res[0].properties["id"] == "C_p2_0"


def test_geometry_normalisation(gateway, cassette, tmp_path):
    from shapely.geometry import box

    record(
        "all",
        cassette,
        tmp_path,
        lambda: gateway.search(geom=box(0, 0, 1, 1), collection="C"),
    )
    replay(
        cassette, tmp_path, lambda: gateway.search(geom=box(0, 0, 1, 1), collection="C")
    )
    replay(
        cassette,
        tmp_path,
        lambda: gateway.search(geom=box(0, 0, 1, 1).wkt, collection="C"),
    )
    with pytest.raises(NoMatchingRecordError):
        replay(
            cassette,
            tmp_path,
            lambda: gateway.search(geom=box(0, 0, 2, 2), collection="C"),
        )


def test_pure_function_repeated_calls(gateway, cassette, tmp_path):
    def call():
        return gateway.search(collection="C")

    record("all", cassette, tmp_path, lambda: (call(), call()))
    assert len(fake.CALLS["search"]) == 2  # repeated real calls
    data = yaml.safe_load(cassette.read_text())
    assert len(data["search"]) == 1  # only one entry (the first wins)
    rec = recorder("none", cassette, tmp_path)
    with rec.patched():
        for _ in range(3):  # endless replay, stateless
            assert len(call()) == 3


def test_errors_in_result_recorded(gateway, cassette, tmp_path):
    record("all", cassette, tmp_path, lambda: gateway.search(collection="PARTIAL"))
    res = replay(cassette, tmp_path, lambda: gateway.search(collection="PARTIAL"))
    assert len(res.errors) == 1  # le TimeOutError n'est pas enregistré
    provider, exc = res.errors[0]
    assert provider == "other_provider" and type(exc) is RequestError
    assert "partial failure" in str(exc)


@pytest.mark.parametrize(
    "collection, exc_type", [("BOOM", RequestError), ("UNAVAILABLE", NotAvailableError)]
)
def test_raised_errors_recorded(gateway, cassette, tmp_path, collection, exc_type):
    def call():
        with pytest.raises(exc_type):
            gateway.search(collection=collection)

    record("all", cassette, tmp_path, call)
    os.environ["FAKE_FORBID"] = "1"
    try:
        replay(cassette, tmp_path, call)
    finally:
        del os.environ["FAKE_FORBID"]


def test_timeout_not_recorded(gateway, cassette, tmp_path):
    def call():
        with pytest.raises(TimeOutError):
            gateway.search(collection="TIMEOUT")

    record("all", cassette, tmp_path, call)
    assert not cassette.exists()  # rien à écrire


# -------------------------------------------------------------- search_all --
def test_search_all_single_entry(gateway, cassette, tmp_path):
    def call():
        return gateway.search_all(collection="C", start="2024-01-01")

    real = record("all", cassette, tmp_path, call)
    assert len(real) == 6
    data = yaml.safe_load(cassette.read_text())
    assert list(data) == [
        "version",
        "search_all",
    ]  # le search() interne n'est pas enregistré
    assert len(data["search_all"]) == 1

    os.environ["FAKE_FORBID"] = "1"
    try:
        replayed = replay(cassette, tmp_path, call)
    finally:
        del os.environ["FAKE_FORBID"]
    assert [p.properties["id"] for p in replayed] == [p.properties["id"] for p in real]
    assert replayed.number_matched == 6


# ---------------------------------------------------------------- download --
def _clean_windows_symlink_pathnames(pathname: str) -> str:
    """
    Workaround symlink pathname under windows.
    See: https://github.com/python/cpython/issues/87123
    """
    _PREFIX = "\\\\?\\"
    if pathname.startswith(_PREFIX):
        return pathname[len(_PREFIX) :]
    return pathname


def test_clean_windows_symlink_pathnames():
    """
    Workaround we cannot test the function from from its docstring with doctest :(
    """
    assert _clean_windows_symlink_pathnames("") == ""

    path = "D:\\a\\eodag\\eodag"
    assert _clean_windows_symlink_pathnames(path) == path

    winsympath = "\\\\?\\D:\\a\\eodag\\eodag"
    assert _clean_windows_symlink_pathnames(winsympath) == path


def test_download_symlink_roundtrip(gateway, cassette, tmp_path):
    def flow():
        product = gateway.search(collection="C")[0]
        return gateway.download(product)

    virtual = record("all", cassette, tmp_path, flow)
    default_out = tmp_path / "default_out"
    assert virtual == str(default_out / "C_p1_0")
    assert (default_out / "C_p1_0").is_symlink()
    assert (
        tmp_path / "archive" / "C_p1_0" / "data.txt"
    ).read_text() == "content of C_p1_0"
    assert fake.CALLS["download"] == ["C_p1_0"]

    # replay on another system : other outpout directory
    other = fake.make_gateway(tmp_path / "other_out")
    os.environ["FAKE_FORBID"] = "1"
    try:
        path = replay(
            cassette, tmp_path, lambda: other.download(other.search(collection="C")[0])
        )
    finally:
        del os.environ["FAKE_FORBID"]
    assert path == str(tmp_path / "other_out" / "C_p1_0")
    assert (Path(path) / "data.txt").read_text() == "content of C_p1_0"
    assert Path(path).is_symlink()
    assert _clean_windows_symlink_pathnames(os.readlink(path)) == str(
        tmp_path / "archive" / "C_p1_0"
    )

    data = yaml.safe_load(cassette.read_text())
    assert data["download"] == [
        {
            "params": {"id": "C_p1_0", "provider": "fake_provider"},
            "result": {"path": "C_p1_0"},
        }
    ]


def test_download_explicit_output_dir_and_existing_link(gateway, cassette, tmp_path):
    out = tmp_path / "explicit"

    def flow():
        return gateway.download(gateway.search(collection="C")[1], output_dir=str(out))

    path = record("all", cassette, tmp_path, flow)
    assert path == str(out / "C_p1_1") and Path(path).is_symlink()
    # 2nd replay: link already exists -> we suppose the product downloaded
    assert replay(cassette, tmp_path, flow) == path
    # broken link: we rebuild
    Path(path).unlink()
    os.symlink(tmp_path / "nowhere", path)
    assert (Path(replay(cassette, tmp_path, flow)) / "data.txt").exists()


def test_download_missing_archive(gateway, cassette, tmp_path):
    def flow():
        return gateway.download(gateway.search(collection="C")[0])

    record("all", cassette, tmp_path, flow)
    import shutil

    shutil.rmtree(tmp_path / "archive" / "C_p1_0")
    with pytest.raises(EodagRecordingError, match="not found"):
        replay(cassette, tmp_path, flow)


def test_download_not_archived_is_not_recorded(gateway, cassette, tmp_path):
    from eodag.api.product import EOProduct

    product = EOProduct(
        "fake_provider",
        {"id": "LOCAL_1", "title": "x", "geometry": fake.POLY},
        collection="C",
    )
    with pytest.warns(EodagRecordingWarning, match="outside of the archive directory"):
        path = record("all", cassette, tmp_path, lambda: gateway.download(product))
    assert path == "/somewhere/else/local_file"
    assert not cassette.exists()


# ------------------------------------------------------------------- modes --
def test_mode_none_missing_cassette(gateway, cassette, tmp_path):
    with pytest.raises(NoMatchingRecordError, match="No 'search' entry"):
        replay(cassette, tmp_path, lambda: gateway.search(collection="C"))
    # no eodag call, a test doesn't fail
    replay(cassette, tmp_path, lambda: None)


def test_mode_once(gateway, cassette, tmp_path):
    def call():
        return gateway.search(collection="C")

    record("once", cassette, tmp_path, call)
    assert len(fake.CALLS["search"]) == 1 and cassette.exists()
    record("once", cassette, tmp_path, call)  # exist -> replay
    assert len(fake.CALLS["search"]) == 1
    with pytest.raises(NoMatchingRecordError):  # unknown -> error
        record("once", cassette, tmp_path, lambda: gateway.search(collection="D"))


def test_mode_all_rewrites(gateway, cassette, tmp_path):
    record("all", cassette, tmp_path, lambda: gateway.search(collection="A"))
    record("all", cassette, tmp_path, lambda: gateway.search(collection="B"))
    data = yaml.safe_load(cassette.read_text())
    assert [e["params"]["collection"] for e in data["search"]] == ["B"]


def test_mode_new_episodes_completes(gateway, cassette, tmp_path):
    record("all", cassette, tmp_path, lambda: gateway.search(collection="A"))
    n = len(fake.CALLS["search"])
    record(
        "new_episodes",
        cassette,
        tmp_path,
        lambda: (gateway.search(collection="A"), gateway.search(collection="B")),
    )
    assert len(fake.CALLS["search"]) == n + 1  # only B is real
    data = yaml.safe_load(cassette.read_text())
    assert sorted(e["params"]["collection"] for e in data["search"]) == ["A", "B"]


def test_no_write_when_test_failed(gateway, cassette, tmp_path):
    record(
        "all", cassette, tmp_path, lambda: gateway.search(collection="C"), save=False
    )
    assert not cassette.exists()


# --------------------------------------------------------- several cassettes --
def test_multiple_cassettes(gateway, tmp_path):
    a, b = tmp_path / "a.yaml", tmp_path / "b.yaml"
    record("all", a, tmp_path, lambda: gateway.search(collection="A"))
    record("all", b, tmp_path, lambda: gateway.search(collection="B"))
    n = len(fake.CALLS["search"])

    def both():
        return (gateway.search(collection="A"), gateway.search(collection="B"))

    replay(None, tmp_path, both, cassettes=[a, b])
    assert len(fake.CALLS["search"]) == n


def test_multiple_cassettes_write_to_required(tmp_path):
    a, b = tmp_path / "a.yaml", tmp_path / "b.yaml"
    for mode in ("all", "new_episodes", "once"):
        with pytest.raises(EodagRecordingConfigError, match="write_to"):
            EodagRecorder(mode, [a, b], tmp_path / "ar")
    EodagRecorder("none", [a, b], tmp_path / "ar")  # read only: OK
    with pytest.raises(EodagRecordingConfigError, match="shall be one of"):
        EodagRecorder("all", [a, b], tmp_path / "ar", write_to=tmp_path / "c.yaml")


def test_duplicate_key_between_cassettes(gateway, tmp_path):
    a, b = tmp_path / "a.yaml", tmp_path / "b.yaml"
    record("all", a, tmp_path, lambda: gateway.search(collection="A"))
    record("all", b, tmp_path, lambda: gateway.search(collection="A"))
    with pytest.raises(DuplicateKeyError):
        EodagRecorder("none", [a, b], tmp_path / "ar")


def test_all_ignores_other_cassettes_with_warning(gateway, tmp_path):
    a, b = tmp_path / "a.yaml", tmp_path / "b.yaml"
    record("all", a, tmp_path, lambda: gateway.search(collection="A"))
    with pytest.warns(EodagRecordingWarning, match="ignored"):
        record(
            "all",
            b,
            tmp_path,
            lambda: gateway.search(collection="A"),
            cassettes=[a, b],
            write_to=b,
        )  # no DuplicateKeyError: a is ignored


def test_cassette_file_format(gateway, cassette, tmp_path):
    record(
        "all",
        cassette,
        tmp_path,
        lambda: gateway.search(collection="C", start="2024-01-01", count=True),
    )
    text = cassette.read_text()
    assert text.startswith("version: 1\n")
    assert "&id" not in text and "*id" not in text  # no YAML alias
    data = yaml.safe_load(text)
    entry = data["search"][0]
    assert entry["params"] == {"collection": "C", "start": "2024-01-01", "count": True}
    assert entry["result"]["products"][0]["geometry"] == fake.POLY
    assert Cassette.load(cassette).entries["search"]


def test_cannot_patch_twice(tmp_path, cassette):
    rec1, rec2 = (
        recorder("none", cassette, tmp_path),
        recorder("none", cassette, tmp_path),
    )
    with rec1.patched():
        with pytest.raises(EodagRecordingError, match="already been patched"):
            with rec2.patched():
                pass
