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
import re
from typing import Callable

from eodag.utils.exceptions import ValidationError


def _tokenize(expr: str) -> list[str]:
    """
    Tokenizes a search expression into words, logical operators, and quoted phrases.

    Handles:
    - Logical operators: AND, OR, NOT
    - Quoted phrases: "exact phrase"
    - Wildcards: * and ? inside words
    - Parentheses: (, )

    :param expr: The search string (e.g., '("foo" OR bar) AND baz')
    :return: A list of tokens (e.g., ['(', '"foo"', 'OR', 'BAR', ')', 'AND', 'BAZ'])

    >>> _tokenize('("foo* bar?" OR baz) AND qux')
    ['(', '"foo* bar?"', 'OR', 'BAZ', ')', 'AND', 'QUX']
    """
    # Match quoted phrases or unquoted tokens (including * and ?), or parentheses
    pattern = r'"[^"]*"|AND|OR|NOT|\(|\)|[^\s()"]+'
    raw_tokens = re.findall(pattern, expr)

    tokens = []
    for token in raw_tokens:
        if token.startswith('"') and token.endswith('"'):
            tokens.append(token)
        elif token.upper() in {"AND", "OR", "NOT"}:
            tokens.append(token.upper())
        else:
            tokens.append(token.upper())
    return tokens


def _to_postfix(tokens: list[str]) -> list[str]:
    """
    Converts infix tokens to postfix (Reverse Polish Notation) using the Shunting Yard algorithm.

    :param tokens: List of tokens in infix order.
    :return: List of tokens in postfix order.

    :raises ValidationError: If parentheses are unbalanced.

    >>> _to_postfix(['FOO', 'AND', '(', 'BAR', 'OR', 'BAZ', ')'])
    ['FOO', 'BAR', 'BAZ', 'OR', 'AND']

    >>> _to_postfix(['(', 'FOO', 'AND', 'BAR'])
    Traceback (most recent call last):
        ...
    eodag.utils.exceptions.ValidationError: Mismatched parentheses in expression
    """
    precedence = {"NOT": 3, "AND": 2, "OR": 1}
    output: list[str] = []
    stack: list[str] = []

    for token in tokens:
        if token in precedence:
            while (
                stack
                and stack[-1] != "("
                and precedence.get(stack[-1], 0) >= precedence[token]
            ):
                output.append(stack.pop())
            stack.append(token)
        elif token == "(":
            stack.append(token)
        elif token == ")":
            while stack and stack[-1] != "(":
                output.append(stack.pop())
            if not stack:
                raise ValidationError("Mismatched parentheses in expression")
            # Remove '('
            stack.pop()
        else:
            output.append(token)

    while stack:
        if stack[-1] == "(":
            raise ValidationError("Mismatched parentheses in expression")
        output.append(stack.pop())

    return output


def _make_evaluator(postfix_expr: list[str]) -> Callable[[dict[str, str]], bool]:
    """
    Returns a function that evaluates a postfix expression on a dictionary of string fields.

    Quoted phrases are matched exactly (case-insensitive).
    Unquoted tokens are matched as case-insensitive full words.

    :param postfix_expr: List of tokens in postfix order.
    :return: A function that returns True if the dict matches.

    >>> evaluator = _make_evaluator(['FOO', 'BAR', 'OR'])
    >>> evaluator({'title': 'some foo text'})
    True
    >>> evaluator({'title': 'some bar text'})
    True
    >>> evaluator({'title': 'nothing'})
    False
    >>> evaluator2 = _make_evaluator(['"foo text"', 'NOT'])
    >>> evaluator2({'title': 'some foo text'})
    False
    >>> evaluator2({'title': 'some bar'})
    True
    """

    def evaluate(entry: dict[str, str]) -> bool:
        stack: list[bool] = []
        text = " ".join(str(v) for v in entry.values()).lower()

        for token in postfix_expr:
            if token == "AND":
                b, a = stack.pop(), stack.pop()
                stack.append(a and b)
            elif token == "OR":
                b, a = stack.pop(), stack.pop()
                stack.append(a or b)
            elif token == "NOT":
                a = stack.pop()
                stack.append(not a)
            else:
                if token.startswith('"') and token.endswith('"'):
                    phrase = token[1:-1].lower()
                    stack.append(phrase in text)
                else:
                    # Convert wildcard token to regex
                    wildcard_pattern = (
                        re.escape(token.lower())
                        .replace(r"\*", ".*")
                        .replace(r"\?", ".")
                    )
                    stack.append(
                        bool(re.search(wildcard_pattern, text, flags=re.IGNORECASE))
                    )

        return stack[0]

    return evaluate


def compile_free_text_query(query: str) -> Callable[[dict[str, str]], bool]:
    """
    Compiles a free-text logical search query into a dictionary evaluator function.

    This is performed in three steps:
    - Parses the query into tokens
    - Converts infix (tokens) to postfix
    - Generates a predicate function from postfix

    Supports:
    - Logical operators: AND, OR, NOT
    - Exact phrases in quotes: "foo bar"
    - Case-insensitive matching

    :param query: A logical expression (e.g., '("foo bar" OR baz) AND qux')
    :return: A function that takes a dictionary of string fields and returns True if it matches.

    :Example:

    >>> evaluator = compile_free_text_query('("FooAndBar" OR BAR) AND "titleFOOBAR - Lorem FOOBAR collection"')
    >>> evaluator({
    ...     "title": "titleFOOBAR - Lorem FOOBAR collection",
    ...     "abstract": "abstract FOOBAR - This is FOOBAR. FooAndBar"
    ... })
    True

    >>> evaluator({"title": "Only Bar here"})
    False

    >>> evaluator = compile_free_text_query('foo*')
    >>> evaluator({"title": "this is foobar"})
    True
    """
    tokens = _tokenize(query)
    postfix = _to_postfix(tokens)
    return _make_evaluator(postfix)
