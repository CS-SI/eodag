# -*- coding: utf-8 -*-
# Copyright 2024, CS Systemes d'Information, https://www.csgroup.eu/
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
from typing import List

from whoosh.matching import NullMatcher
from whoosh.qparser import OrGroup, QueryParser, plugins
from whoosh.query.positional import Phrase
from whoosh.query.qcore import QueryError


class RobustPhrase(Phrase):
    """
    Matches documents containing a given phrase.
    """

    def matcher(self, searcher, context=None):
        """
        Override the default to not raise error on match exception but simply return not found
        Needed to handle phrase search in whoosh.fields.IDLIST
        """
        try:
            return super().matcher(searcher, context)
        except QueryError:
            return NullMatcher()


class EODAGQueryParser(QueryParser):
    """
    A hand-written query parser built on modular plug-ins.

    Override the default to include specific EODAG configuration
    """

    def __init__(
        self,
        filters: List[str],
        schema,
    ):
        super().__init__(
            None,
            schema=schema,
            plugins=[
                plugins.SingleQuotePlugin(),
                plugins.FieldsPlugin(),
                plugins.WildcardPlugin(),
                plugins.PhrasePlugin(),
                plugins.GroupPlugin(),
                plugins.OperatorsPlugin(),
                plugins.BoostPlugin(),
                plugins.EveryPlugin(),
                plugins.RangePlugin(),
                plugins.PlusMinusPlugin(),
                plugins.MultifieldPlugin(filters, fieldboosts=None),
            ],
            phraseclass=RobustPhrase,
            group=OrGroup,
        )
