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
  deploy-wsgi-app  Configure the settings of the HTTP web app (the
                   providers...
  discover         Fetch providers to discover product types
  download         Download a list of products from a serialized search...
  list             List supported product types
  search           Search satellite images by their product types,...
  serve-rest       Start eodag HTTP server
  serve-rpc        Start eodag rpc server
  version          Print eodag version and exit

  noqa: D103
"""
import json
import os
import shutil
import sys
import textwrap

try:
    from importlib.metadata import metadata  # type: ignore
except ImportError:  # pragma: no cover
    # for python < 3.8
    from importlib_metadata import metadata  # type: ignore

from typing import Any, Dict, List, Mapping, Set

import click
import uvicorn
from click import Context

from eodag.api.core import EODataAccessGateway
from eodag.utils import DEFAULT_ITEMS_PER_PAGE, DEFAULT_PAGE, parse_qs
from eodag.utils.exceptions import NoMatchingProductType, UnsupportedProvider
from eodag.utils.logging import setup_logging

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
        self, ctx: Context, opts: Mapping[str, Any], args: List[str]
    ):
        """Raise error or use parent handle_parse_result()"""
        if self.mutually_exclusive.intersection(opts) and self.name in opts:
            raise click.UsageError(
                "Illegal usage: `{}` is mutually exclusive with "
                "arguments `{}`.".format(self.name, ", ".join(self.mutually_exclusive))
            )

        return super(MutuallyExclusiveOption, self).handle_parse_result(ctx, opts, args)


@click.group()
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
    help="Search satellite images by their product types, instrument, platform, "
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
@click.option(
    "-c",
    "--cloudCover",
    type=click.IntRange(0, 100),
    help="Maximum cloud cover percentage needed for the product",
)
@click.option("-p", "--productType", help="The product type to search")
@click.option("-i", "--instrument", help="Search for products matching this instrument")
@click.option("-P", "--platform", help="Search for products matching this platform")
@click.option(
    "-t",
    "--platformSerialIdentifier",
    help="Search for products originating from the satellite identified by this keyword",
)
@click.option(
    "-L", "--processingLevel", help="Search for products matching this processing level"
)
@click.option(
    "-S", "--sensorType", help="Search for products matching this type of sensor"
)
@click.option("--id", help="Search for the product identified by this id")
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
@click.pass_context
def search_crunch(ctx: Context, **kwargs: Any) -> None:
    """Search product types and optionnaly apply crunchers to search results"""
    # Process inputs for search
    product_type = kwargs.pop("producttype")
    instrument = kwargs.pop("instrument")
    platform = kwargs.pop("platform")
    platform_identifier = kwargs.pop("platformserialidentifier")
    processing_level = kwargs.pop("processinglevel")
    sensor_type = kwargs.pop("sensortype")
    id_ = kwargs.pop("id")
    locations_qs = kwargs.pop("locations")
    custom = kwargs.pop("query")
    if not any(
        [
            product_type,
            instrument,
            platform,
            platform_identifier,
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
        "geometry": footprint,
        "startTimeFromAscendingNode": None,
        "completionTimeFromAscendingNode": None,
        "cloudCover": kwargs.pop("cloudcover"),
        "productType": product_type,
        "instrument": instrument,
        "platform": platform,
        "platformSerialIdentifier": platform_identifier,
        "processingLevel": processing_level,
        "sensorType": sensor_type,
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
        criteria["startTimeFromAscendingNode"] = start_date.isoformat()
    if stop_date:
        criteria["completionTimeFromAscendingNode"] = stop_date.isoformat()
    conf_file = kwargs.pop("conf")
    if conf_file:
        conf_file = click.format_filename(conf_file)
    locs_file = kwargs.pop("locs")
    if locs_file:
        locs_file = click.format_filename(locs_file)

    # Process inputs for crunch
    cruncher_names: Set[Any] = set(kwargs.pop("cruncher") or [])
    cruncher_args = kwargs.pop("cruncher_args")
    cruncher_args_dict: Dict[str, Dict[str, Any]] = {}
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
        results, total = gateway.search(
            page=page, items_per_page=items_per_page, **criteria
        )
        click.echo("Found a total number of {} products".format(total))
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


@eodag.command(name="list", help="List supported product types")
@click.option("-p", "--provider", help="List product types supported by this provider")
@click.option(
    "-i", "--instrument", help="List product types originating from this instrument"
)
@click.option(
    "-P", "--platform", help="List product types originating from this platform"
)
@click.option(
    "-t",
    "--platformSerialIdentifier",
    help="List product types originating from the satellite identified by this keyword",
)
@click.option("-L", "--processingLevel", help="List product types of processing level")
@click.option(
    "-S", "--sensorType", help="List product types originating from this type of sensor"
)
@click.option(
    "--no-fetch", is_flag=True, help="Do not fetch providers for new product types"
)
@click.pass_context
def list_pt(ctx: Context, **kwargs: Any) -> None:
    """Print the list of supported product types"""
    setup_logging(verbose=ctx.obj["verbosity"])
    dag = EODataAccessGateway()
    provider = kwargs.pop("provider")
    fetch_providers = not kwargs.pop("no_fetch")
    text_wrapper = textwrap.TextWrapper()
    guessed_product_types = []
    try:
        guessed_product_types = dag.guess_product_type(
            platformSerialIdentifier=kwargs.get("platformserialidentifier"),
            processingLevel=kwargs.get("processinglevel"),
            sensorType=kwargs.get("sensortype"),
            **kwargs,
        )
    except NoMatchingProductType:
        if any(
            kwargs[arg]
            for arg in [
                "instrument",
                "platform",
                "platformserialidentifier",
                "processinglevel",
                "sensortype",
            ]
        ):
            click.echo("No product type match the following criteria you provided:")
            click.echo(
                "\n".join(
                    "-{param}={value}".format(**locals())
                    for param, value in kwargs.items()
                    if value is not None
                )
            )
            sys.exit(1)
    try:
        if guessed_product_types:
            product_types = [
                pt
                for pt in dag.list_product_types(
                    provider=provider, fetch_providers=fetch_providers
                )
                if pt["ID"] in guessed_product_types
            ]
        else:
            product_types = dag.list_product_types(
                provider=provider, fetch_providers=fetch_providers
            )
        click.echo("Listing available product types:")
        for product_type in product_types:
            click.echo("\n* {}: ".format(product_type["ID"]))
            for prop, value in product_type.items():
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


@eodag.command(name="discover", help="Fetch providers to discover product types")
@click.option("-p", "--provider", help="Fetch only the given provider")
@click.option(
    "--storage",
    type=click.Path(dir_okay=False, writable=True, readable=False),
    default="ext_product_types.json",
    help="Path to the file where to store external product types configuration "
    "(.json extension will be automatically appended to the filename). "
    "DEFAULT: ext_product_types.json",
)
@click.pass_context
def discover_pt(ctx: Context, **kwargs: Any) -> None:
    """Fetch external product types configuration and save result"""
    setup_logging(verbose=ctx.obj["verbosity"])
    dag = EODataAccessGateway()
    provider = kwargs.pop("provider")

    ext_product_types_conf = (
        dag.discover_product_types(provider=provider)
        if provider
        else dag.discover_product_types()
    )

    storage_filepath = kwargs.pop("storage")
    if not storage_filepath.endswith(".json"):
        storage_filepath += ".json"
    with open(storage_filepath, "w") as f:
        json.dump(ext_product_types_conf, f)
    click.echo("Results stored at '{}'".format(storage_filepath))


@eodag.command(help="Download a list of products from a serialized search result")
@click.option(
    "--search-results",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to a serialized search result",
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
@click.pass_context
def download(ctx: Context, **kwargs: Any) -> None:
    """Download a bunch of products from a serialized search result"""
    search_result_path = kwargs.pop("search_results")
    if not search_result_path:
        with click.Context(download) as ctx:
            click.echo("Nothing to do (no search results file provided)")
            click.echo(download.get_help(ctx))
        sys.exit(1)
    setup_logging(verbose=ctx.obj["verbosity"])
    conf_file = kwargs.pop("conf")
    if conf_file:
        conf_file = click.format_filename(conf_file)

    satim_api = EODataAccessGateway(user_conf_file_path=conf_file)
    search_results = satim_api.deserialize(search_result_path)

    get_quicklooks = kwargs.pop("quicklooks")
    if get_quicklooks:
        click.echo(
            "Flag 'quicklooks' specified, downloading only quicklooks of products"
        )

        for idx, product in enumerate(search_results):
            if product.downloader is None:
                auth = product.downloader_auth
                if auth is None:
                    auth = satim_api._plugins_manager.get_auth_plugin(product.provider)
                search_results[idx].register_downloader(
                    satim_api._plugins_manager.get_download_plugin(product), auth
                )

            downloaded_file = product.get_quicklook()
            if not downloaded_file:
                click.echo(
                    "A quicklook may have been downloaded but we cannot locate it. "
                    "Increase verbosity for more details: `eodag -v download [OPTIONS]`"
                )
            else:
                click.echo("Downloaded {}".format(downloaded_file))

    else:
        # register downloader
        for idx, product in enumerate(search_results):
            if product.downloader is None:
                auth = product.downloader_auth
                if auth is None:
                    auth = satim_api._plugins_manager.get_auth_plugin(product.provider)
                search_results[idx].register_downloader(
                    satim_api._plugins_manager.get_download_plugin(product), auth
                )

        downloaded_files = satim_api.download_all(search_results)
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


@eodag.command(help="Start eodag rpc server")
@click.option(
    "-h",
    "--host",
    type=click.STRING,
    default="localhost",
    help="Interface where to listen for requests",
)
@click.option(
    "-p",
    "--port",
    type=click.INT,
    default=50051,
    help="The port where to listen for requests",
)
@click.option(
    "-f",
    "--conf",
    type=click.Path(exists=True),
    help="File path to the user configuration file with its credentials",
)
@click.pass_context
def serve_rpc(ctx: Context, host: str, port: int, conf: str) -> None:
    """Serve EODAG functionalities through a RPC interface"""
    setup_logging(verbose=ctx.obj["verbosity"])
    try:
        from eodag_cube.rpc.server import EODAGRPCServer
    except ImportError:
        raise NotImplementedError(
            "eodag-cube needed for this functionnality, install using `pip install eodag-cube`"
        )

    server = EODAGRPCServer(host, port, conf)
    server.serve()


@eodag.command(
    help="Start eodag HTTP server\n\n"
    "Set EODAG_CORS_ALLOWED_ORIGINS environment variable to configure Cross-Origin Resource Sharing allowed origins as "
    "comma-separated URLs (e.g. 'http://somewhere,htttp://somewhere.else')."
)
@click.option(
    "-f",
    "--config",
    type=click.Path(exists=True, resolve_path=True),
    help="File path to the user configuration file with its credentials, default is ~/.config/eodag/eodag.yml",
)
@click.option(
    "-l",
    "--locs",
    type=click.Path(exists=True, resolve_path=True),
    required=False,
    help="File path to the location shapefiles configuration file",
)
@click.option(
    "-d", "--daemon", is_flag=True, show_default=True, help="run in daemon mode"
)
@click.option(
    "-w",
    "--world",
    is_flag=True,
    show_default=True,
    help=(
        "run uvicorn using IPv4 0.0.0.0 (all network interfaces), "
        "otherwise bind to 127.0.0.1 (localhost). "
    ),
)
@click.option(
    "-p",
    "--port",
    type=int,
    default=5000,
    show_default=True,
    help="The port on which to listen",
)
@click.option(
    "--debug",
    is_flag=True,
    show_default=True,
    help="Run in debug mode (for development purpose)",
)
@click.pass_context
def serve_rest(
    ctx: Context,
    daemon: bool,
    world: bool,
    port: int,
    config: str,
    locs: str,
    debug: bool,
) -> None:
    """Serve EODAG functionalities through a WEB interface"""
    setup_logging(verbose=ctx.obj["verbosity"])
    # Set the settings of the app
    # IMPORTANT: the order of imports counts here (first we override the settings,
    # then we import the app so that the updated settings is taken into account in
    # the app initialization)
    if config:
        os.environ["EODAG_CFG_FILE"] = config

    if locs:
        os.environ["EODAG_LOCS_CFG_FILE"] = locs

    bind_host = "127.0.0.1"
    if world:
        bind_host = "0.0.0.0"
    if daemon:
        try:
            pid = os.fork()
        except OSError as e:
            raise Exception("%s [%d]" % (e.strerror, e.errno))

        if pid == 0:
            os.setsid()
            uvicorn.run("eodag.rest.server:app", host=bind_host, port=port)
        else:
            sys.exit(0)
    else:
        logging_config = uvicorn.config.LOGGING_CONFIG
        if debug:
            logging_config["loggers"]["uvicorn"]["level"] = "DEBUG"
            logging_config["loggers"]["uvicorn.error"]["level"] = "DEBUG"
            logging_config["loggers"]["uvicorn.access"]["level"] = "DEBUG"
            logging_config["formatters"]["default"][
                "fmt"
            ] = "%(asctime)-15s %(name)-32s [%(levelname)-8s] (%(module)-17s) %(message)s"
            logging_config["loggers"]["eodag"] = {
                "handlers": ["default"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            }
        uvicorn.run(
            "eodag.rest.server:app",
            host=bind_host,
            port=port,
            reload=debug,
            log_config=logging_config,
        )


@eodag.command(
    help="Configure the settings of the HTTP web app (the providers credential "
    "files essentially) and copy the web app source directory into the "
    "specified directory"
)
@click.option(
    "--root",
    type=click.Path(exists=True, resolve_path=True),
    default="/var/www/",
    show_default=True,
    help="The directory where to deploy the webapp (a subdirectory with the name "
    "from --name option will be created there)",
)
@click.option(
    "-f",
    "--config",
    type=click.Path(exists=True, resolve_path=True),
    required=True,
    help="File path to the user configuration file with its credentials",
)
@click.option(
    "--webserver",
    type=click.Choice(["apache"]),
    default="apache",
    show_default=True,
    help="The webserver for which to generate sample configuration",
)
@click.option(
    "--threads",
    type=int,
    default=5,
    show_default=True,
    help="Number of threads for apache webserver config (ignored if not apache "
    "webserver)",
)
@click.option(
    "--user",
    type=str,
    default="www-data",
    show_default=True,
    help="The user of the webserver",
)
@click.option(
    "--group",
    type=str,
    default="www-data",
    show_default=True,
    help="The group of the webserver",
)
@click.option(
    "--server-name",
    type=str,
    default="localhost",
    show_default=True,
    help="The name to give to the server",
)
@click.option(
    "--wsgi-process-group",
    type=str,
    default="eodag-server",
    show_default=True,
    help="The name of the wsgi process group (ignored if not apache webserver",
)
@click.option(
    "--wsgi-daemon-process",
    type=str,
    default="eodag-server",
    show_default=True,
    help="The name of the wsgi daemon process (ignored if not apache webserver",
)
@click.option(
    "--name",
    type=str,
    default="eodag_server",
    show_default=True,
    help="The name of the directory that will be created in the webserver root "
    "directory to host the WSGI app",
)
@click.pass_context
def deploy_wsgi_app(
    ctx: Context,
    root: str,
    config: str,
    webserver: str,
    threads: int,
    user: str,
    group: str,
    server_name: str,
    wsgi_process_group: str,
    wsgi_daemon_process: str,
    name: str,
) -> None:
    """Deploy the WEB interface of eodag behind a web server"""
    setup_logging(verbose=ctx.obj["verbosity"])
    import eodag as eodag_package

    server_config = {"EODAG_CFG_FILE": config}
    eodag_package_path = eodag_package.__path__[0]
    webapp_src_path = os.path.join(eodag_package_path, "rest")
    webapp_dst_path = os.path.join(root, name)
    if not os.path.exists(webapp_dst_path):
        os.mkdir(webapp_dst_path)
    wsgi_path = os.path.join(webapp_dst_path, "server.wsgi")
    click.echo(
        "Moving eodag HTTP web app from {} to {}".format(
            webapp_src_path, webapp_dst_path
        )
    )
    shutil.copy(os.path.join(webapp_src_path, "server.wsgi"), wsgi_path)

    click.echo(
        "Overriding eodag HTTP server config with values: {}".format(server_config)
    )
    with open(os.path.join(webapp_dst_path, "eodag_server_settings.json"), "w") as fd:
        json.dump(server_config, fd)

    click.echo("Finished ! The WSGI file is in {}".format(wsgi_path))
    if webserver == "apache":
        application_group = "%{GLOBAL}"
        apache_config_sample = (
            """
<VirtualHost *>
    ServerName %(server_name)s

    WSGIDaemonProcess %(wsgi_daemon_process)s user=%(user)s group=%(group)s \
    threads=%(threads)s
    WSGIScriptAlias / %(wsgi_path)s

    <Directory %(webapp_dst_path)s>
        WSGIProcessGroup %(wsgi_process_group)s
        WSGIApplicationGroup %(application_group)s
        <IfVersion < 2.4>
            Order allow,deny
            Allow from all
        </IfVersion>
        <IfVersion >= 2.4>
            Require all granted
        </IfVersion>
    </Directory>
</VirtualHost>
        """
            % locals()
        )
        click.echo("Sample Apache2 config to add in a your virtual host:")
        click.echo(apache_config_sample)


if __name__ == "__main__":
    eodag(obj={})
