# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
#
# This file is part of EODAG project
#     https://www.github.com/CS-SI/EODAG
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""EODAG Command Line interface

Usage: eodag [OPTIONS] COMMAND [ARGS]...

  Earth Observation Data Access Gateway: work on EO products from any
  provider

Options:
  -v, --verbose  Control the verbosity of the logs. For maximum verbosity,
                 type -vvv
  --help         Show this message and exit.

Commands:
  discover         Fetch providers to discover collections
  download         Download a list of products from a serialized search...
  list             List supported collections
  search           Search satellite images by their collections,...
  version          Print eodag version and exit

  noqa: D103
"""

from __future__ import annotations

import functools
import json
import sys
import textwrap
from importlib.metadata import metadata
from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional
from urllib.parse import parse_qs

import click

from eodag.api.core import EODataAccessGateway, SearchResult
from eodag.utils import DEFAULT_ITEMS_PER_PAGE, DEFAULT_PAGE
from eodag.utils.exceptions import NoMatchingCollection, UnsupportedProvider
from eodag.utils.logging import setup_logging

if TYPE_CHECKING:
    from click import Context

# A list of supported crunchers that the user can choose (see --cruncher option below)
CRUNCHERS = [
    "FilterLatestByName",
    "FilterLatestIntersect",
    "FilterOverlap",
    "FilterProperty",
    "FilterDate",
]


class MutuallyExclusiveOption(click.Option):
    """Mutually Exclusive Options for Click
    from https://gist.github.com/jacobtolar/fb80d5552a9a9dfc32b12a829fa21c0c
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.mutually_exclusive = set(kwargs.pop("mutually_exclusive", []))
        help = kwargs.get("help", "")
        if self.mutually_exclusive:
            ex_str = ", ".join(self.mutually_exclusive)
            kwargs["help"] = help + (
                " NOTE: This argument is mutually exclusive with "
                " arguments: [" + ex_str + "]."
            )
        super(MutuallyExclusiveOption, self).__init__(*args, **kwargs)

    def handle_parse_result(
        self, ctx: Context, opts: Mapping[str, Any], args: list[str]
    ):
        """Raise error or use parent handle_parse_result()"""
        if self.mutually_exclusive.intersection(opts) and self.name in opts:
            raise click.UsageError(
                "Illegal usage: `{}` is mutually exclusive with arguments `{}`.".format(
                    self.name, ", ".join(self.mutually_exclusive)
                )
            )

        return super(MutuallyExclusiveOption, self).handle_parse_result(ctx, opts, args)


def _deprecated_cli(message: str, version: Optional[str] = None) -> Callable[..., Any]:
    """Decorator to mark a CLI command as deprecated and print a bold yellow warning."""
    version_msg = f" -- Deprecated since v{version}" if version else ""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            full_message = f"DEPRECATED: {message}{version_msg}"
            click.echo(click.style(full_message, fg="yellow", bold=True), err=True)
            return func(*args, **kwargs)

        return wrapper

    return decorator


@click.group(chain=True)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Control the verbosity of the logs. For maximum verbosity, type -vvv",
)
@click.pass_context
def eodag(ctx: Context, verbose: int) -> None:
    """Earth Observation Data Access Gateway: work on EO products from any provider"""
    if ctx.obj is None:
        ctx.obj = {}
    ctx.obj["verbosity"] = verbose


@eodag.command(name="version", help="Print eodag version and exit")
def version() -> None:
    """Print eodag version and exit"""
    click.echo(
        "{__title__} ({__description__}): version {__version__}".format(
            __title__=metadata("eodag")["Name"],
            __description__=metadata("eodag")["Summary"],
            __version__=metadata("eodag")["Version"],
        )
    )


@eodag.command(
    name="search",
    help="Search satellite images by their collections, instrument, platform, "
    "platform identifier, processing level or sensor type. It is mandatory to provide "
    "at least one of the previous criteria for eodag to perform a search. "
    "Optionally crunch the search results before storing them in a geojson file",
)
@click.option(
    "-f",
    "--conf",
    help="File path to the user configuration file with its credentials, default is ~/.config/eodag/eodag.yml",
    type=click.Path(exists=True),
)
@click.option(
    "-l",
    "--locs",
    help="File path to the user locations configuration file, default is ~/.config/eodag/locations.yml",
    type=click.Path(exists=True),
)
@click.option("-p", "--provider", help="Search on this provider")
@click.option(
    "-b",
    "--box",
    type=(float,) * 4,
    default=(None,) * 4,
    cls=MutuallyExclusiveOption,
    mutually_exclusive=["geom"],
    help="Search for a product on a bounding box, providing its minlon, minlat, "
    "maxlon and maxlat (in this order).",
)
@click.option(
    "-g",
    "--geom",
    cls=MutuallyExclusiveOption,
    mutually_exclusive=["box"],
    help="Search for a product on a geometry, providing its WKT representation.",
)
@click.option(
    "-s",
    "--start",
    type=click.DateTime(),
    help="Start sensing time in ISO8601 format (e.g. '1990-11-26', '1990-11-26T14:30:10'). UTC is assumed",
)
@click.option(
    "-e",
    "--end",
    type=click.DateTime(),
    help="End sensing time in ISO8601 format (e.g. '1990-11-26', '1990-11-26T14:30:10'). UTC is assumed",
)
@click.option("-c", "--collection", help="The collection to search")
@click.option("--instruments", help="Search for products matching these instruments")
@click.option("--platform", help="Search for products matching this platform")
@click.option("--constellation", help="Search for products matching this constellation")
@click.option(
    "--processing-level", help="Search for products matching this processing level"
)
@click.option("--sensor-type", help="Search for products matching this type of sensor")
@click.option(
    "--cloud-cover",
    type=click.IntRange(0, 100),
    help="Maximum cloud cover percentage needed for the product",
)
@click.option("--id", help="Search for the product identified by this id")
@click.option(
    "--locations",
    type=str,
    help="Custom query-string argument(s) to select locations. "
    "Format :'key1=value1&key2=value2'. Example: --locations country=FRA&continent=Africa",
)
@click.option(
    "-q",
    "--query",
    type=str,
    help="Custom query-string argument(s). Format :'key1=value1&key2=value2'",
)
@click.option(
    "--cruncher",
    type=click.Choice(CRUNCHERS),
    multiple=True,
    help="A cruncher to be applied to search results. Repeat option many times to "
    "apply many crunchers",
)
@click.option(
    "--cruncher-args",
    type=(str,) * 3,
    multiple=True,
    help="Named arguments acting as the parameters of a cruncher. "
    "Enter it like this: --cruncher-args <CruncherName> <arg-name> <arg-value>. "
    "Repeat option many times to give many args to a cruncher",
)
@click.option(
    "--storage",
    type=click.Path(dir_okay=False, writable=True, readable=False),
    default="search_results.geojson",
    help="Path to the file where to store search results (.geojson extension will be "
    "automatically appended to the filename). DEFAULT: search_results.geojson",
)
@click.option(
    "--items",
    type=int,
    show_default=False,
    help="The number of items to return. Eodag is bound to whatever limitation the "
    "providers have on the number of results they return. This option allows "
    "to control how many items eodag should request "
    f"[default: {DEFAULT_ITEMS_PER_PAGE}]",
)
@click.option(
    "--page",
    type=int,
    default=DEFAULT_PAGE,
    show_default=True,
    help="Retrieve the given page",
)
@click.option(
    "--all",
    is_flag=True,
    help="Retrieve ALL the products that match the search criteria. It collects "
    "products by iterating over the results pages until no more products are available."
    "At each iteration, the maximum number of items searched is either 'items' if set, "
    "or a maximum value defined internally for the requested provider, or a default "
    "maximum value equals to 50.",
)
@click.option(
    "--count",
    is_flag=True,
    help="Make a count request together with search (Enabling count will significantly "
    "slow down search requests for some providers, and might be unavailable for some"
    "others).",
)
@click.pass_context
def search_crunch(ctx: Context, **kwargs: Any) -> None:
    """Search collections and optionnaly apply crunchers to search results"""
    # Process inputs for search
    provider = kwargs.pop("provider")
    collection = kwargs.pop("collection")
    instruments = kwargs.pop("instruments")
    platform = kwargs.pop("platform")
    constellation = kwargs.pop("constellation")
    processing_level = kwargs.pop("processing_level")
    sensor_type = kwargs.pop("sensor_type")
    id_ = kwargs.pop("id")
    locations_qs = kwargs.pop("locations")
    custom = kwargs.pop("query")
    if not any(
        [
            collection,
            instruments,
            platform,
            constellation,
            processing_level,
            sensor_type,
            id_,
        ]
    ):
        with click.Context(search_crunch) as ctx:
            print("Give me some work to do. See below for how to do that:", end="\n\n")
            click.echo(search_crunch.get_help(ctx))
        sys.exit(-1)

    setup_logging(verbose=ctx.obj["verbosity"])

    if kwargs["box"] != (None,) * 4:
        rect = kwargs.pop("box")
        footprint = {
            "lonmin": rect[0],
            "latmin": rect[1],
            "lonmax": rect[2],
            "latmax": rect[3],
        }
    else:
        footprint = kwargs.pop("geom")

    start_date = kwargs.pop("start")
    stop_date = kwargs.pop("end")
    criteria = {
        "provider": provider,
        "geometry": footprint,
        "start_datetime": None,
        "end_datetime": None,
        "eo:cloud_cover": kwargs.pop("cloud_cover"),
        "collection": collection,
        "instruments": instruments,
        "constellation": constellation,
        "platform": platform,
        "processing:level": processing_level,
        "eodag:sensor_type": sensor_type,
        "id": id_,
    }
    if custom:
        custom_dict = parse_qs(custom)
        for k, v in custom_dict.items():
            if isinstance(v, list) and len(v) == 1:
                criteria[k] = v[0]
            else:
                criteria[k] = v
    if locations_qs is not None:
        locations = {key: val[0] for key, val in parse_qs(locations_qs).items()}
    else:
        locations = None
    criteria["locations"] = locations
    if start_date:
        criteria["start_datetime"] = start_date.isoformat()
    if stop_date:
        criteria["end_datetime"] = stop_date.isoformat()
    conf_file = kwargs.pop("conf")
    if conf_file:
        conf_file = click.format_filename(conf_file)
    locs_file = kwargs.pop("locs")
    if locs_file:
        locs_file = click.format_filename(locs_file)

    count = kwargs.pop("count")

    # Process inputs for crunch
    cruncher_names: set[Any] = set(kwargs.pop("cruncher") or [])
    cruncher_args = kwargs.pop("cruncher_args")
    cruncher_args_dict: dict[str, dict[str, Any]] = {}
    if cruncher_args:
        for cruncher, argname, argval in cruncher_args:
            cruncher_args_dict.setdefault(cruncher, {}).setdefault(argname, argval)

    items_per_page = kwargs.pop("items")
    page = kwargs.pop("page") or 1

    gateway = EODataAccessGateway(
        user_conf_file_path=conf_file, locations_conf_path=locs_file
    )

    # Search
    get_all_products = kwargs.pop("all")
    if get_all_products:
        # search_all needs items_per_page to be None if the user lets eodag determines
        # what value it should take.
        items_per_page = None if items_per_page is None else items_per_page
        results = gateway.search_all(items_per_page=items_per_page, **criteria)
    else:
        # search should better take a value that is not None
        items_per_page = (
            DEFAULT_ITEMS_PER_PAGE if items_per_page is None else items_per_page
        )
        results = gateway.search(
            count=count, page=page, items_per_page=items_per_page, **criteria
        )
        if results.number_matched is not None:
            click.echo(
                "Found a total number of {} products".format(results.number_matched)
            )
    click.echo("Returned {} products".format(len(results)))

    # Crunch !
    crunch_args = {
        cruncher_name: cruncher_args_dict.get(cruncher_name, {})
        for cruncher_name in cruncher_names
    }
    if crunch_args:
        results = gateway.crunch(results, search_criteria=criteria, **crunch_args)

    storage_filepath = kwargs.pop("storage")
    if not storage_filepath.endswith(".geojson"):
        storage_filepath += ".geojson"
    result_storage = gateway.serialize(results, filename=storage_filepath)
    click.echo("Results stored at '{}'".format(result_storage))
    ctx.obj["search_results"] = results


@eodag.command(name="list", help="List supported collections")
@click.option("-p", "--provider", help="List collections supported by this provider")
@click.option(
    "--instruments", help="List collections originating from these instruments"
)
@click.option("--platform", help="List collections originating from this platform")
@click.option(
    "--constellation",
    help="List collections originating from this constellation",
)
@click.option("--processing-level", help="List collections of processing level")
@click.option(
    "--sensor-type", help="List collections originating from this type of sensor"
)
@click.option(
    "--no-fetch", is_flag=True, help="Do not fetch providers for new collections"
)
@click.pass_context
def list_pt(ctx: Context, **kwargs: Any) -> None:
    """Print the list of supported collections"""
    setup_logging(verbose=ctx.obj["verbosity"])
    dag = EODataAccessGateway()
    provider = kwargs.pop("provider")
    fetch_providers = not kwargs.pop("no_fetch")
    text_wrapper = textwrap.TextWrapper()
    guessed_collections = []
    try:
        guessed_collections = dag.guess_collection(
            **kwargs,
        )
    except NoMatchingCollection:
        if any(
            kwargs[arg]
            for arg in [
                "instruments",
                "constellation",
                "platform",
                "processing_level",
                "sensor_type",
            ]
        ):
            click.echo("No collection match the following criteria you provided:")
            click.echo(
                "\n".join(
                    "-{param}={value}".format(**locals())
                    for param, value in kwargs.items()
                    if value is not None
                )
            )
            sys.exit(1)
    try:
        if guessed_collections:
            collections = [
                pt
                for pt in dag.list_collections(
                    provider=provider, fetch_providers=fetch_providers
                )
                if pt["ID"] in guessed_collections
            ]
        else:
            collections = dag.list_collections(
                provider=provider, fetch_providers=fetch_providers
            )
        click.echo("Listing available collections:")
        for collection in collections:
            click.echo("\n* {}: ".format(collection["ID"]))
            for prop, value in collection.items():
                if prop != "ID":
                    text_wrapper.initial_indent = "    - {}: ".format(prop)
                    text_wrapper.subsequent_indent = " " * len(
                        text_wrapper.initial_indent
                    )
                    if value is not None:
                        click.echo(text_wrapper.fill(str(value)))
    except UnsupportedProvider:
        click.echo("Unsupported provider. You may have a typo")
        click.echo(
            "Available providers: {}".format(", ".join(dag.available_providers()))
        )
        sys.exit(1)


@eodag.command(name="discover", help="Fetch providers to discover collections")
@click.option("-p", "--provider", help="Fetch only the given provider")
@click.option(
    "--storage",
    type=click.Path(dir_okay=False, writable=True, readable=False),
    default="ext_collections.json",
    help="Path to the file where to store external collections configuration "
    "(.json extension will be automatically appended to the filename). "
    "DEFAULT: ext_collections.json",
)
@click.pass_context
def discover_pt(ctx: Context, **kwargs: Any) -> None:
    """Fetch external collections configuration and save result"""
    setup_logging(verbose=ctx.obj["verbosity"])
    dag = EODataAccessGateway()
    provider = kwargs.pop("provider")

    ext_collections_conf = (
        dag.discover_collections(provider=provider)
        if provider
        else dag.discover_collections()
    )

    storage_filepath = kwargs.pop("storage")
    if not storage_filepath.endswith(".json"):
        storage_filepath += ".json"
    with open(storage_filepath, "w") as f:
        json.dump(ext_collections_conf, f)
    click.echo("Results stored at '{}'".format(storage_filepath))


@eodag.command(
    help="""Download a list of products from a serialized search result or STAC items URLs/paths

Examples:

  eodag download --search-results /path/to/search_results.geojson

  eodag download --stac-item https://example.com/stac/item1.json --stac-item /path/to/item2.json
""",
)
@click.option(
    "--search-results",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to a serialized search result",
)
@click.option(
    "--stac-item",
    multiple=True,
    help="URL/path of a STAC item to download (multiple values accepted)",
)
@click.option(
    "-f",
    "--conf",
    type=click.Path(exists=True),
    help="File path to the user configuration file with its credentials, default is ~/.config/eodag/eodag.yml",
)
@click.option(
    "--quicklooks",
    is_flag=True,
    show_default=False,
    help="Download only quicklooks of products instead full set of files",
)
@click.option(
    "--output-dir",
    type=click.Path(dir_okay=True, file_okay=False),
    help="Products or quicklooks download directory (Default: local temporary directory)",
)
@click.pass_context
def download(ctx: Context, **kwargs: Any) -> None:
    """Download a bunch of products from a serialized search result"""
    search_result_path = kwargs.pop("search_results")
    stac_items = kwargs.pop("stac_item")
    search_results = ctx.obj.get("search_results")
    if not search_result_path and not stac_items and search_results is None:
        with click.Context(download) as ctx:
            click.echo("Nothing to do (no search results file or stac item provided)")
            click.echo(download.get_help(ctx))
        sys.exit(1)
    setup_logging(verbose=ctx.obj["verbosity"])
    conf_file = kwargs.pop("conf")
    if conf_file:
        conf_file = click.format_filename(conf_file)

    satim_api = EODataAccessGateway(user_conf_file_path=conf_file)

    search_results = search_results or SearchResult([])
    if search_result_path:
        search_results.extend(satim_api.deserialize_and_register(search_result_path))
    if stac_items:
        search_results.extend(satim_api.import_stac_items(list(stac_items)))

    output_dir = kwargs.pop("output_dir")
    get_quicklooks = kwargs.pop("quicklooks")

    if get_quicklooks:
        # Download only quicklooks
        click.echo(
            "Flag 'quicklooks' specified, downloading only quicklooks of products"
        )

        for idx, product in enumerate(search_results):
            downloaded_file = product.get_quicklook(output_dir=output_dir)
            if not downloaded_file:
                click.echo(
                    "A quicklook may have been downloaded but we cannot locate it. "
                    "Increase verbosity for more details: `eodag -v download [OPTIONS]`"
                )
            else:
                click.echo("Downloaded {}".format(downloaded_file))

    else:
        # Download products
        downloaded_files = satim_api.download_all(search_results, output_dir=output_dir)
        if downloaded_files and len(downloaded_files) > 0:
            for downloaded_file in downloaded_files:
                if downloaded_file is None:
                    click.echo(
                        "A file may have been downloaded but we cannot locate it"
                    )
                else:
                    click.echo("Downloaded {}".format(downloaded_file))
        else:
            click.echo(
                "Error during download, a file may have been downloaded but we cannot locate it"
            )


if __name__ == "__main__":
    eodag(obj={})
