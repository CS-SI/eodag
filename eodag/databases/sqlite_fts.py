# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, https://www.csgroup.eu/
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
"""SQLite FTS5 query parser for STAC q expressions."""

import re
from typing import cast

_FTS_TOKEN_RE = re.compile(
    r'"(?:[^"\\]|\\.)*"|\(|\)|\bAND\b|\bOR\b|[^\s()"]+',
    flags=re.IGNORECASE,
)

_UNSUPPORTED_PREFIX_RE = re.compile(r"^[+-]")

_PRECEDENCE = {"OR": 1, "AND": 2}
_SYNTAX = frozenset(_PRECEDENCE) | {"(", ")"}


def _quote_fts_term(term: str) -> str:
    """Quote a term for FTS5, escaping internal double quotes by doubling them."""
    t = term.strip()
    if t.startswith('"') and t.endswith('"'):
        return t
    escaped = t.replace('"', '""')
    return f'"{escaped}"'


def _normalize_tokens(q: str) -> list[str]:
    """Tokenize, reject +/-, insert implicit OR between adjacent operands."""
    raw = cast(list[str], _FTS_TOKEN_RE.findall(q.strip()))
    if not raw:
        return []

    out: list[str] = []
    for tok in raw:
        up = tok.upper()
        if up in _SYNTAX:
            out.append(up)
            continue

        if _UNSUPPORTED_PREFIX_RE.match(tok):
            raise ValueError(
                f"Unsupported operator '{tok[0]}' in q expression. "
                "Use AND / OR / parentheses instead."
            )

        out.append(_quote_fts_term(tok))

    # Insert implicit OR (default STAC behavior)
    with_or: list[str] = []
    for i, tok in enumerate(out):
        with_or.append(tok)
        if i < len(out) - 1:
            nxt = out[i + 1]
            left_is_end = tok not in _SYNTAX or tok == ")"
            right_is_start = nxt not in _SYNTAX or nxt == "("
            if left_is_end and right_is_start:
                with_or.append("OR")

    return with_or


def _to_postfix(tokens: list[str]) -> list[str]:
    """Shunting-yard for left-associative binary AND / OR."""
    out: list[str] = []
    ops: list[str] = []

    for tok in tokens:
        if tok not in _SYNTAX:
            out.append(tok)
        elif tok == "(":
            ops.append(tok)
        elif tok == ")":
            while ops and ops[-1] != "(":
                out.append(ops.pop())
            if not ops:
                raise ValueError("Unbalanced parentheses")
            ops.pop()
        else:  # AND / OR
            while (
                ops
                and ops[-1] != "("
                and _PRECEDENCE.get(ops[-1], 0) >= _PRECEDENCE[tok]
            ):
                out.append(ops.pop())
            ops.append(tok)

    while ops:
        if ops[-1] in {"(", ")"}:
            raise ValueError("Unbalanced parentheses")
        out.append(ops.pop())

    return out


def _postfix_to_fts5(postfix: list[str]) -> str:
    """Build FTS5 expression directly from postfix tokens."""
    stack: list[str] = []

    for tok in postfix:
        if tok not in _PRECEDENCE:
            stack.append(tok)
        else:
            if len(stack) < 2:
                raise ValueError(f"Missing operand for operator {tok}")
            rhs = stack.pop()
            lhs = stack.pop()
            stack.append(f"({lhs}) {tok} ({rhs})")

    if len(stack) != 1:
        raise ValueError("Invalid expression")
    return stack[0]


def stac_q_to_fts5(q: str) -> str:
    """
    Parser for STAC q expressions.

    Supported syntax:
    - bare terms (implicit OR between adjacent terms)
    - quoted phrases ("exact phrase")
    - explicit AND / OR operators
    - parentheses for grouping

    + and - prefix operators are not supported and will raise ValueError.
    """
    tokens = _normalize_tokens(q)
    if not tokens:
        return ""
    postfix = _to_postfix(tokens)
    return _postfix_to_fts5(postfix)
