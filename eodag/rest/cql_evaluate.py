from datetime import datetime as dt
from typing import Any, Dict, List, Optional, Union

from pygeofilter import ast
from pygeofilter.backends.evaluator import Evaluator, handle
from pygeofilter.values import Geometry, Interval


class EodagEvaluator(Evaluator):
    """
    Evaluate a cql2 json expression and transform it to a STAC args object
    """

    def __init__(self) -> None:
        self.search_obj = {}

    @handle(ast.Attribute, Interval, str, int, float)
    def attribute(
        self, node: Union[str, ast.Attribute, Interval], *_
    ) -> Union[str, ast.Attribute, Interval]:
        """handle attribute and literal"""
        return node

    @handle(Geometry)
    def spatial(self, node: Geometry) -> Dict[str, Any]:
        """handle geometry"""
        return node.geometry

    @handle(dt)
    def temporal(self, node: dt) -> str:
        """handle datetime"""
        return node.isoformat()

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
            raise SyntaxError(f"First element in {node} must be the property")

        if isinstance(node, (ast.Equal, ast.GeometryIntersects)):
            return {lhs.name: rhs}

        if isinstance(node, ast.LessEqual):
            if not isinstance(node.rhs, dt):
                raise SyntaxError("<= is only supported for datetime")
            return {"end_datetime": rhs}

        if isinstance(node, ast.GreaterEqual):
            if not isinstance(node.rhs, dt):
                raise SyntaxError(">= is only supported for datetime")
            return {"start_datetime": rhs}

        if isinstance(node, ast.TimeOverlaps):
            return {"start_datetime": rhs[0], "end_datetime": rhs[1]}

        return None

    @handle(ast.In)
    def contains(self, node: ast.In, lhs: Any, *rhs: Any):
        """handle in keyword"""
        return {lhs.name: list(rhs)}

    @handle(ast.And)
    def combination(self, _, lhs: Dict[str, str], rhs: Dict[str, str]):
        """handle combinations"""
        return {**lhs, **rhs}
