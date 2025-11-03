#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2025, CS GROUP - France, https://www.csgroup.eu/
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
"""
Compare two ext_collections.json files and group differences by JSON paths.
"""

import json
import sys
from collections import defaultdict
from typing import Set


def get_all_paths(obj, path=""):
    """Get all JSON paths and their values from a nested object."""
    paths = {}

    if isinstance(obj, dict):
        for key, value in obj.items():
            new_path = f"{path}.{key}" if path else key
            if isinstance(value, (dict, list)):
                paths.update(get_all_paths(value, new_path))
            else:
                paths[new_path] = value
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            new_path = f"{path}[{i}]"
            if isinstance(value, (dict, list)):
                paths.update(get_all_paths(value, new_path))
            else:
                paths[new_path] = value
    else:
        paths[path] = obj

    return paths


def find_differing_paths(obj1, obj2) -> Set[str]:
    """Find all JSON paths where two objects differ."""
    paths1 = get_all_paths(obj1)
    paths2 = get_all_paths(obj2)

    all_paths = set(paths1.keys()) | set(paths2.keys())
    differing_paths = set()

    for path in all_paths:
        val1 = paths1.get(path, "<MISSING>")
        val2 = paths2.get(path, "<MISSING>")
        if val1 != val2:
            differing_paths.add(path)

    return differing_paths


def format_diff(obj1, obj2, indent=4):
    """Format a simple diff between two objects."""
    import difflib

    json1 = json.dumps(obj1, indent=indent, sort_keys=True)
    json2 = json.dumps(obj2, indent=indent, sort_keys=True)

    diff = list(
        difflib.unified_diff(
            json1.splitlines(keepends=True),
            json2.splitlines(keepends=True),
            fromfile="old",
            tofile="new",
            n=3,
        )
    )

    return "".join(diff)


def compare_collections(
    file1_path: str, file2_path: str, include_details: bool = True, job_url: str = ""
):
    """Compare two ext_collections.json files.

    Args:
        file1_path: Path to the old/reference JSON file
        file2_path: Path to the new JSON file
        include_details: Whether to include detailed diff content in collapsible sections
        job_url: URL to the job summary for linking from light version
    """  # Load JSON files
    try:
        with open(file1_path) as f:
            data1 = json.load(f)
        with open(file2_path) as f:
            data2 = json.load(f)
    except Exception as e:
        print(f"Error loading files: {e}", file=sys.stderr)
        return

    # 1. Compare providers (top-level keys)
    providers1 = set(data1.keys())
    providers2 = set(data2.keys())

    if providers1 != providers2:
        print("\n### Providers:")
        print("```diff")
        for provider in sorted(providers1 - providers2):
            print(f"- {provider}")
        for provider in sorted(providers2 - providers1):
            print(f"+ {provider}")
        print("```")

    # 2. Group differences by changed paths
    path_groups = defaultdict(list)  # path_set -> [(provider, type, item, diff)]

    # Compare each provider
    common_providers = providers1 & providers2
    for provider in sorted(common_providers):
        provider_data1 = data1[provider]
        provider_data2 = data2[provider]

        # Compare providers_config items content (no list diff, just content)
        providers_config1 = set(provider_data1.get("providers_config", {}).keys())
        providers_config2 = set(provider_data2.get("providers_config", {}).keys())

        # Compare each providers_config item's content
        common_provider_configs = providers_config1 & providers_config2
        for item in sorted(common_provider_configs):
            prov_conf1 = provider_data1["providers_config"][item]
            prov_conf2 = provider_data2["providers_config"][item]

            if prov_conf1 != prov_conf2:
                differing_paths = find_differing_paths(prov_conf1, prov_conf2)
                if differing_paths:
                    # Use sorted tuple of paths as key for grouping
                    path_key = tuple(sorted(differing_paths))
                    diff_content = format_diff(prov_conf1, prov_conf2)
                    path_groups[path_key].append(
                        (provider, "providers_config", item, diff_content)
                    )

        # Compare collection lists
        collections1 = set(provider_data1.get("collections_config", {}).keys())
        collections2 = set(provider_data2.get("collections_config", {}).keys())

        if collections1 != collections2:
            print(f"\n#### {provider} - collections:")
            print("```diff")
            for collection in sorted(collections1 - collections2):
                print(f"- {collection}")
            for collection in sorted(collections2 - collections1):
                print(f"+ {collection}")
            print("```")

        # Compare each collection's content
        common_collections = collections1 & collections2
        for collection in sorted(common_collections):
            coll1 = provider_data1["collections_config"][collection]
            coll2 = provider_data2["collections_config"][collection]

            if coll1 != coll2:
                differing_paths = find_differing_paths(coll1, coll2)
                if differing_paths:
                    # Use sorted tuple of paths as key for grouping
                    path_key = tuple(sorted(differing_paths))
                    diff_content = format_diff(coll1, coll2)
                    path_groups[path_key].append(
                        (provider, "collections_config", collection, diff_content)
                    )

    # 3. Display grouped results
    if path_groups:
        print("\n - - - \n")
        print("### Changes grouped by JSON paths:")

        for path_set, items in sorted(path_groups.items()):
            # Show the paths that changed
            paths_formatted = "`\n`".join(path_set)

            # Create anchor for this path group (for linking from light version)
            path_anchor = (
                "-".join(path_set)
                .replace(".", "")
                .replace("[", "")
                .replace("]", "")
                .replace("/", "-")
            )

            print(f'\n<a id="path-{path_anchor}"></a>')
            print(f"`{paths_formatted}`")

            # Get unique providers for this path group
            providers = sorted(set(item[0] for item in items))
            providers_text = f" ({', '.join(providers)})" if providers else ""

            # Show collection count with providers
            print(f"**{len(items)} collection(s) affected{providers_text}**")

            if include_details:
                # Make item list collapsible with detailed diffs
                print("<details>")
                print("<summary>Click to expand for detailed diffs</summary>")
                print()

                # Show each affected item
                for provider, config_type, item_name, diff_content in items:
                    print(f"##### {provider} - {config_type} - {item_name}")
                    print("```diff")
                    print(diff_content.rstrip())
                    print("```")
                    print()

                print("</details>")
            else:
                # Light version: show details if ≤10 collections, otherwise link to detailed version
                if len(items) <= 10:
                    # Show collapsible details like in full version
                    print("<details>")
                    print("<summary>Click to expand for detailed diffs</summary>")
                    print()

                    # Show each affected item with diffs
                    for provider, config_type, item_name, diff_content in items:
                        print(f"##### {provider} - {config_type} - {item_name}")
                        print("```diff")
                        print(diff_content.rstrip())
                        print("```")
                        print()

                    print("</details>")
                else:
                    # Too many items, just link to the detailed anchor in job summary
                    print(
                        "\n_Too many collections to list here. See "
                        f"[detailed breakdown in job summary]({job_url}#path-{path_anchor}) "
                        "for the complete list._"
                    )
                    print()

            print("\n - - - \n")

    # Summary
    total_changes = sum(len(items) for items in path_groups.values())
    total_paths = len(path_groups)

    print("### Summary:")
    print(
        f"- {total_changes} item(s) with changes (providers_config + collections_config)"
    )
    print(f"- {total_paths} unique path pattern(s)")


def main():
    """Main entry point for the collections comparison script."""
    if len(sys.argv) < 3:
        print(
            "Usage: python ext_collections_cmp.py <old.json> <new.json> [--no-details] [--job-url=URL]"
        )
        sys.exit(1)

    include_details = "--no-details" not in sys.argv

    # Extract job URL if provided
    job_url = ""
    for arg in sys.argv:
        if arg.startswith("--job-url="):
            job_url = arg.split("=", 1)[1]
            break

    compare_collections(sys.argv[1], sys.argv[2], include_details, job_url)


if __name__ == "__main__":
    main()
