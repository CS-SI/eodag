# -*- coding: utf-8 -*-
# Copyright 2023, CS Systemes d'Information, https://www.csgroup.eu/
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
from datetime import datetime as dt
from typing import Any, Dict, List, Optional, Tuple, Union

from pygeofilter import ast
from pygeofilter.backends.evaluator import Evaluator, handle
from pygeofilter.values import Geometry, Interval

simpleNode = Union[ast.Attribute, str, int, complex, float, List[Any], Tuple[Any, ...]]


class EodagEvaluator(Evaluator):
    """
    Evaluate a cql2 json expression and transform it to a STAC args object
    """

    @handle(ast.Attribute, str, int, complex, float, list, tuple)
    def attribute(self, node: simpleNode, *_) -> simpleNode:
        """handle attribute and literal"""
        return node

    @handle(Geometry)
    def spatial(self, node: Geometry) -> Dict[str, Any]:
        """handle geometry"""
        return node.geometry

    @handle(dt)
    def temporal(self, node: dt) -> str:
        """handle datetime"""
        return node.strftime("%Y-%m-%dT%H:%M:%SZ")

    @handle(Interval)
    def interval(self, _, *interval: Any) -> List[Any]:
        """handle datetime interval"""
        return list(interval)

    @handle(
        ast.GeometryIntersects,
        ast.Equal,
        ast.LessEqual,
        ast.GreaterEqual,
        ast.TimeOverlaps,
        ast.In,
    )
    def predicate(
        self, node: ast.Predicate, lhs: Any, rhs: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Handle predicates
        Verify the property is first attribute in each predicate
        """
        if not isinstance(lhs, ast.Attribute):
            raise ValueError(
                f'invalid cql syntax, first argument in "{node.op.value}" must be a property'
            )

        if isinstance(node, ast.Equal) and not isinstance(
            rhs, (int, float, complex, str)
        ):
            raise ValueError(
                f'second argument in property "{lhs.name}" must be a string or a numeric value'
            )

        if isinstance(node, ast.GeometryIntersects) and not lhs.name == "geometry":
            raise ValueError(
                f'operator {node.op.value} is not supported for property "{lhs.name}"'
            )

        if isinstance(node, (ast.Equal, ast.GeometryIntersects)):
            return {lhs.name: rhs}

        if isinstance(node, ast.LessEqual):
            if not isinstance(node.rhs, dt):
                raise ValueError(
                    f'operator "<=" is not supported for property "{lhs.name}"'
                )
            return {"end_datetime": rhs}

        if isinstance(node, ast.GreaterEqual):
            if not isinstance(node.rhs, dt):
                raise ValueError(
                    f'operator ">=" is not supported for property "{lhs.name}"'
                )
            return {"start_datetime": rhs}

        if isinstance(node, ast.TimeOverlaps):
            return {"start_datetime": rhs[0], "end_datetime": rhs[1]}

        return None

    @handle(ast.In)
    def contains(self, node: ast.In, lhs: Any, *rhs: Any):
        """handle in keyword"""
        if not isinstance(node.sub_nodes, list):  # type: ignore
            raise ValueError(
                f'property "{lhs.name}" expects a value in list format with operator "in"'
            )
        return {lhs.name: list(rhs)}

    @handle(ast.And)
    def combination(self, _, lhs: Dict[str, str], rhs: Dict[str, str]):
        """handle combinations"""
        return {**lhs, **rhs}
