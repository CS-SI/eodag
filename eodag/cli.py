# -*- coding: utf-8 -*-
# Copyright 2018, CS Systemes d'Information, http://www.c-s.fr
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
  download         Download a list of products from a serialized search...
  list             List supported product types
  search           Search satellite images by their product types,...
  serve-rest       Start eodag HTTP server
  serve-rpc        Start eodag rpc server

  noqa: D103
"""
from __future__ import absolute_import, print_function, unicode_literals

import json
import os
import shutil
import sys
import textwrap

import click

from eodag.api.core import DEFAULT_ITEMS_PER_PAGE, DEFAULT_PAGE, EODataAccessGateway
from eodag.utils.exceptions import NoMatchingProductType, UnsupportedProvider
from eodag.utils.logging import setup_logging

# disable warning on Python 2
click.disable_unicode_literals_warning = True

# A list of supported crunchers that the user can choose (see --cruncher option below)
CRUNCHERS = ["FilterLatestByName", "FilterLatestIntersect", "FilterOverlap"]


@click.group()
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Control the verbosity of the logs. For maximum verbosity, type -vvv",
)
@click.pass_context
def eodag(ctx, verbose):
    """Earth Observation Data Access Gateway: work on EO products from any provider"""
    if ctx.obj is None:
        ctx.obj = {}
    ctx.obj["verbosity"] = verbose


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
    help="File path to the user configuration file with its credentials",
    type=click.Path(exists=True),
)
@click.option(
    "-b",
    "--box",
    type=(float,) * 4,
    default=(None,) * 4,
    help="Search for a product on a bounding box, providing its minlon, minlat, "
    "maxlon and maxlat (in this order)",
)
@click.option(
    "-s",
    "--start",
    type=click.DateTime(),
    help="Maximum age of the product (in ISO8601 format: yyyy-MM-ddThh:mm:ss.SSSZ)",
)
@click.option(
    "-e",
    "--end",
    type=click.DateTime(),
    help="Minimum age of the product (in ISO8601 format: yyyy-MM-ddThh:mm:ss.SSSZ)",
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
    default=DEFAULT_ITEMS_PER_PAGE,
    show_default=True,
    help="The number of items to return. Eodag is bound to whatever limitation the "
    "providers have on the number of results they return. This option allows "
    "to control how many items eodag should request",
)
@click.option(
    "--page",
    type=int,
    default=DEFAULT_PAGE,
    show_default=True,
    help="Retrieve the given page",
)
@click.pass_context
def search_crunch(ctx, **kwargs):
    """Search product types and optionnaly apply crunchers to search results"""
    # Process inputs for search
    product_type = kwargs.pop("producttype")
    instrument = kwargs.pop("instrument")
    platform = kwargs.pop("platform")
    platform_identifier = kwargs.pop("platformserialidentifier")
    processing_level = kwargs.pop("processinglevel")
    sensor_type = kwargs.pop("sensortype")
    if not any(
        [
            product_type,
            instrument,
            platform,
            platform_identifier,
            processing_level,
            sensor_type,
        ]
    ):
        with click.Context(search_crunch) as ctx:
            print("Give me some work to do. See below for how to do that:", end="\n\n")
            click.echo(search_crunch.get_help(ctx))
        sys.exit(-1)

    kwargs["verbose"] = ctx.obj["verbosity"]
    setup_logging(**kwargs)
    if kwargs["box"] != (None,) * 4:
        rect = kwargs.pop("box")
        footprint = {
            "lonmin": rect[0],
            "latmin": rect[1],
            "lonmax": rect[2],
            "latmax": rect[3],
        }
    else:
        footprint = None
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
    }
    if start_date:
        criteria["startTimeFromAscendingNode"] = start_date.isoformat()
    if stop_date:
        criteria["completionTimeFromAscendingNode"] = stop_date.isoformat()
    conf_file = kwargs.pop("conf")
    if conf_file:
        conf_file = click.format_filename(conf_file)

    # Process inputs for crunch
    cruncher_names = set(kwargs.pop("cruncher") or [])
    cruncher_args = kwargs.pop("cruncher_args")
    cruncher_args_dict = {}
    if cruncher_args:
        for cruncher, argname, argval in cruncher_args:
            cruncher_args_dict.setdefault(cruncher, {}).setdefault(argname, argval)

    items_per_page = kwargs.pop("items")
    page = kwargs.pop("page") or 1

    gateway = EODataAccessGateway(user_conf_file_path=conf_file)

    # Search
    results, total = gateway.search(
        page=page, items_per_page=items_per_page, **criteria
    )
    click.echo("Found a total number of {} products".format(total))
    click.echo("Returned {} products".format(len(results), product_type))

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
@click.pass_context
def list_pt(ctx, **kwargs):
    """Print the list of supported product types"""
    setup_logging(verbose=ctx.obj["verbosity"])
    dag = EODataAccessGateway()
    provider = kwargs.pop("provider")
    text_wrapper = textwrap.TextWrapper()
    guessed_product_types = []
    try:
        guessed_product_types = dag.guess_product_type(
            platformSerialIdentifier=kwargs.get("platformserialidentifier"),
            processingLevel=kwargs.get("processinglevel"),
            sensorType=kwargs.get("sensortype"),
            **kwargs
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
                for pt in dag.list_product_types(provider=provider)
                if pt["ID"] in guessed_product_types
            ]
        else:
            product_types = dag.list_product_types(provider=provider)
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
                        click.echo(text_wrapper.fill(value))
    except UnsupportedProvider:
        click.echo("Unsupported provider. You may have a typo")
        click.echo(
            "Available providers: {}".format(", ".join(dag.available_providers()))
        )
        sys.exit(1)


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
    help="File path to the user configuration file with its credentials",
)
@click.pass_context
def download(ctx, **kwargs):
    """Download a bunch of products from a serialized search result"""
    search_result_path = kwargs.pop("search_results")
    if not search_result_path:
        with click.Context(download) as ctx:
            click.echo("Nothing to do (no search results file provided)")
            click.echo(download.get_help(ctx))
        sys.exit(1)
    kwargs["verbose"] = ctx.obj["verbosity"]
    setup_logging(**kwargs)
    conf_file = kwargs.pop("conf")
    if conf_file:
        conf_file = click.format_filename(conf_file)
        satim_api = EODataAccessGateway(user_conf_file_path=conf_file)
        search_results = satim_api.deserialize(search_result_path)
        for downloaded_file in satim_api.download_all(search_results):
            if downloaded_file is None:
                click.echo("A file may have been downloaded but we cannot locate it")
            else:
                click.echo("Downloaded {}".format(downloaded_file))


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
def serve_rpc(ctx, host, port, conf):
    """Serve EODAG functionalities through a RPC interface"""
    setup_logging(verbose=ctx.obj["verbosity"])
    from eodag.rpc.server import EODAGRPCServer

    server = EODAGRPCServer(host, port, conf)
    server.serve()


@eodag.command(help="Start eodag HTTP server")
@click.option(
    "-f",
    "--config",
    type=click.Path(exists=True, resolve_path=True),
    required=True,
    help="File path to the user configuration file with its credentials",
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
        "run flask using IPv4 0.0.0.0 (all network interfaces), "
        "otherwise bind to 127.0.0.1 (localhost). "
        "This maybe necessary in systems that only run Flask"
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
def serve_rest(ctx, daemon, world, port, config, debug):
    """Serve EODAG functionalities through a WEB interface"""
    setup_logging(verbose=ctx.obj["verbosity"])
    # Set the settings of the app
    # IMPORTANT: the order of imports counts here (first we override the settings,
    # then we import the app so that the updated settings is taken into account in
    # the app initialization)
    from eodag.rest import settings

    settings.EODAG_CFG_FILE = config

    from eodag.rest.server import app

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
            app.run(threaded=True, host=bind_host, port=port)
        else:
            sys.exit(0)
    else:
        app.run(debug=debug, host=bind_host, port=port)


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
    ctx,
    root,
    config,
    webserver,
    threads,
    user,
    group,
    server_name,
    wsgi_process_group,
    wsgi_daemon_process,
    name,
):
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
    shutil.copy(
        os.path.join(webapp_src_path, "description.md"),
        os.path.join(webapp_dst_path, "description.md"),
    )
    shutil.copytree(
        os.path.join(webapp_src_path, "templates"),
        os.path.join(webapp_dst_path, "templates"),
    )

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
