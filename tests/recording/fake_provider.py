"""Faux provider pour tester eodag_recording sans réseau.

``install()`` remplace search/search_all/download de EODataAccessGateway par des
implémentations déterministes. Si la variable d'environnement FAKE_FORBID est
définie, tout appel « réel » lève une AssertionError (utile pour vérifier qu'un
rejeu ne contacte pas le provider).
"""

import os
import tempfile
from types import SimpleNamespace

from shapely import wkt

from eodag import EODataAccessGateway, SearchResult
from eodag.api.product import EOProduct
from eodag.utils.exceptions import NotAvailableError, RequestError, TimeOutError

CALLS = {"search": [], "search_all": [], "download": []}
POLY = "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))"
INTERSECTION = "POLYGON ((0 0, 0.5 0, 0.5 0.5, 0 0.5, 0 0))"


def _forbid(name):
    if os.environ.get("FAKE_FORBID"):
        raise AssertionError(
            f"appel réel à {name}() alors que FAKE_FORBID est positionné"
        )


def make_products(collection, page, n):
    products = []
    for i in range(n):
        pid = f"{collection}_p{page}_{i}"
        product = EOProduct(
            "fake_provider",
            {
                "id": pid,
                "title": pid,
                "geometry": POLY,
                "datetime": "2024-01-01T00:00:00Z",
                "eodag:download_link": "https://example.com/dl?token=SECRET",
                "nested": {"b": [1, 2], "a": {"z": 1.5}},
            },
            collection=collection,
        )
        product.search_intersection = wkt.loads(INTERSECTION)
        products.append(product)
    return products


def fake_search(
    self,
    page=1,
    limit=None,
    items_per_page=None,
    raise_errors=False,
    start=None,
    end=None,
    geom=None,
    locations=None,
    provider=None,
    count=False,
    validate=True,
    **kwargs,
):
    _forbid("search")
    CALLS["search"].append((page, kwargs))
    collection = kwargs.get("collection", "C")
    if collection == "BOOM":
        raise RequestError(
            "boom",
        )
    if collection == "TIMEOUT":
        raise TimeOutError("too slow")
    if collection == "UNAVAILABLE":
        raise NotAvailableError("nope")
    errors = []
    if collection == "PARTIAL":
        errors = [
            ("other_provider", RequestError("partial failure")),
            ("third_provider", TimeOutError("not recorded")),
        ]
    # 3 produits sur les pages 1 et 2, puis plus rien
    n = 3 if page in (1, 2) else 0
    return SearchResult(
        make_products(collection, page, n),
        number_matched=6 if count else None,
        errors=errors,
    )


def fake_search_all(
    self,
    limit=None,
    items_per_page=None,
    start=None,
    end=None,
    geom=None,
    locations=None,
    **kwargs,
):
    _forbid("search_all")
    CALLS["search_all"].append(kwargs)
    # comme eodag : la 1ʳᵉ page passe par self.search(), les autres non
    first = self.search(
        page=1,
        limit=limit,
        start=start,
        end=end,
        geom=geom,
        locations=locations,
        **kwargs,
    )
    rest = SearchResult(make_products(kwargs.get("collection", "C"), 2, 3))
    result = SearchResult(list(first) + list(rest))
    result.number_matched = len(result)
    return result


def fake_download(
    self, product, progress_callback=None, executor=None, wait=0.2, timeout=10, **kwargs
):
    _forbid("download")
    CALLS["download"].append(product.properties["id"])
    out = kwargs.get("output_dir") or tempfile.gettempdir()
    if product.properties["id"].startswith("LOCAL"):
        return "/somewhere/else/local_file"
    target = os.path.join(out, product.properties["title"])
    os.makedirs(target, exist_ok=True)
    with open(os.path.join(target, "data.txt"), "w") as fh:
        fh.write(f"content of {product.properties['id']}")
    return target


def install(monkeypatch=None):
    patches = {
        "search": fake_search,
        "search_all": fake_search_all,
        "download": fake_download,
    }
    for name, func in patches.items():
        if monkeypatch is not None:
            monkeypatch.setattr(EODataAccessGateway, name, func)
        else:
            setattr(EODataAccessGateway, name, func)
    for calls in CALLS.values():
        calls.clear()


def make_gateway(default_output_dir):
    """Gateway sans configuration réseau, avec un output_dir par défaut."""
    gateway = EODataAccessGateway.__new__(EODataAccessGateway)
    plugin = SimpleNamespace(config=SimpleNamespace(output_dir=str(default_output_dir)))
    gateway._plugins_manager = SimpleNamespace(
        get_download_plugin=lambda product: plugin
    )
    return gateway
