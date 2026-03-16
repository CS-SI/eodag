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
    Unquoted tokens are matched as case-insensitive full words (unless they contain wildcards).

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
                    # Wildcard tokens → regex with .* and .
                    if "*" in token or "?" in token:
                        wildcard_pattern = (
                            re.escape(token.lower())
                            .replace(r"\*", ".*")
                            .replace(r"\?", ".")
                        )
                        regex = re.compile(wildcard_pattern, flags=re.IGNORECASE)
                    else:
                        # Plain token → must match as a whole word
                        regex = re.compile(
                            rf"\b{re.escape(token.lower())}\b", flags=re.IGNORECASE
                        )

                    stack.append(bool(regex.search(text)))

        return stack[0]

    return evaluate


def compile_free_text_query(query: str) -> Callable[[dict[str, str]], bool]:
    """
    Compiles a free-text logical search query into a dictionary evaluator function.

    The evaluator checks whether the concatenated string values of a dictionary
    (case-insensitive) satisfy the given logical expression.

    Processing steps:
        1. Tokenize the query into words, quoted phrases, wildcards, and operators.
        2. Convert infix tokens into postfix notation using the Shunting Yard algorithm.
        3. Build an evaluator function that applies the expression to dictionary fields.

    Supported features:
        - Logical operators: ``AND``, ``OR``, ``NOT``
        - Grouping with parentheses: ``(``, ``)``
        - Exact phrases in quotes: ``"foo bar"`` (case-insensitive substring match)
        - Wildcards inside tokens:
            - ``*`` → matches zero or more characters
            - ``?`` → matches exactly one character
        - Plain tokens without wildcards → matched as whole words (word boundary aware)
        - Case-insensitive matching across all tokens and phrases

    :param query: A logical search expression
                  (e.g., ``'("foo bar" OR baz*) AND NOT qux'``).
    :return: A function that takes a ``dict[str, str]`` and returns ``True`` if it matches.

    :Example:

    >>> evaluator = compile_free_text_query('("FooAndBar" OR BAR) AND "FOOBAR collection"')
    >>> evaluator({
    ...     "title": "titleFOOBAR - Lorem FOOBAR collection",
    ...     "description": "abstract FOOBAR - This is FOOBAR. FooAndBar"
    ... })
    True
    >>> evaluator({
    ...     "title": "collection FOOBAR",
    ...     "description": "abstract FOOBAR - This is FOOBAR. FooAndBar"
    ... })
    False
    >>> evaluator({
    ...     "title": "titleFOOBAR - Lorem FOOBAR ",
    ...     "description": "abstract FOOBAR - This is FOOBAR."
    ... })
    False
    >>> evaluator({"title": "Only Bar here"})
    False

    Wildcard example:

    >>> evaluator = compile_free_text_query('foo*')
    >>> evaluator({"title": "this is foobar"})
    True
    >>> evaluator({"title": "something with fooo"})
    True
    >>> evaluator({"title": "bar only"})
    False
    """

    tokens = _tokenize(query)
    postfix = _to_postfix(tokens)
    return _make_evaluator(postfix)
