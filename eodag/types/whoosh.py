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
from whoosh.fields import Schema
from whoosh.index import _DEF_INDEX_NAME, FileIndex
from whoosh.matching import NullMatcher
from whoosh.qparser import OrGroup, QueryParser, plugins
from whoosh.query.positional import Phrase
from whoosh.query.qcore import QueryError
from whoosh.util.text import utf8encode
from whoosh.writing import SegmentWriter


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
        filters: list[str],
        schema: Schema,
    ):
        """
        EODAG QueryParser initialization

        :param filters: list of fieldnames to filter on
        :param schema: Whoosh Schema
        """
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


class CleanSegmentWriter(SegmentWriter):
    """Override to clean up writer for failed document add when exceptions were absorbed
    cf: https://github.com/whoosh-community/whoosh/pull/543
    """

    def add_document(self, **fields):
        """Add document"""
        self._check_state()
        perdocwriter = self.perdocwriter
        schema = self.schema
        docnum = self.docnum
        add_post = self.pool.add

        docboost = self._doc_boost(fields)
        fieldnames = sorted(
            [name for name in fields.keys() if not name.startswith("_")]
        )
        self._check_fields(schema, fieldnames)

        perdocwriter.start_doc(docnum)

        try:
            for fieldname in fieldnames:
                value = fields.get(fieldname)
                if value is None:
                    continue
                field = schema[fieldname]

                length = 0
                if field.indexed:
                    # TODO: Method for adding progressive field values, ie
                    # setting start_pos/start_char?
                    fieldboost = self._field_boost(fields, fieldname, docboost)
                    # Ask the field to return a list of (text, weight, vbytes)
                    # tuples
                    items = field.index(value)
                    # Only store the length if the field is marked scorable
                    scorable = field.scorable
                    # Add the terms to the pool
                    for tbytes, freq, weight, vbytes in items:
                        weight *= fieldboost
                        if scorable:
                            length += freq
                        add_post((fieldname, tbytes, docnum, weight, vbytes))

                if field.separate_spelling():
                    spellfield = field.spelling_fieldname(fieldname)
                    for word in field.spellable_words(value):
                        word = utf8encode(word)[0]
                        add_post((spellfield, word, 0, 1, vbytes))

                vformat = field.vector
                if vformat:
                    analyzer = field.analyzer
                    # Call the format's word_values method to get posting values
                    vitems = vformat.word_values(value, analyzer, mode="index")
                    # Remove unused frequency field from the tuple
                    vitems = sorted(
                        (text, weight, vbytes) for text, _, weight, vbytes in vitems
                    )
                    perdocwriter.add_vector_items(fieldname, field, vitems)

                # Allow a custom value for stored field/column
                customval = fields.get("_stored_%s" % fieldname, value)

                # Add the stored value and length for this field to the per-
                # document writer
                sv = customval if field.stored else None
                perdocwriter.add_field(fieldname, field, sv, length)

                column = field.column_type
                if column and customval is not None:
                    cv = field.to_column_value(customval)
                    perdocwriter.add_column_value(fieldname, column, cv)
        except Exception as ex:
            # cancel doc
            perdocwriter._doccount -= 1
            perdocwriter._indoc = False
            raise ex

        perdocwriter.finish_doc()
        self._added = True
        self.docnum += 1


class CleanFileIndex(FileIndex):
    """Override to call CleanSegmentWriter"""

    def writer(self, procs=1, **kwargs):
        """file index writer"""
        if procs > 1:
            from whoosh.multiproc import MpWriter

            return MpWriter(self, procs=procs, **kwargs)
        else:
            return CleanSegmentWriter(self, **kwargs)


def create_in(dirname, schema, indexname=None):
    """
    Override to call the CleanFileIndex.

    Convenience function to create an index in a directory. Takes care of
    creating a FileStorage object for you.

    :param dirname: the path string of the directory in which to create the
        index.
    :param schema: a :class:`whoosh.fields.Schema` object describing the
        index's fields.
    :param indexname: the name of the index to create; you only need to specify
        this if you are creating multiple indexes within the same storage
        object.
    :returns: :class:`Index`
    """

    from whoosh.filedb.filestore import FileStorage

    if not indexname:
        indexname = _DEF_INDEX_NAME
    storage = FileStorage(dirname)
    return CleanFileIndex.create(storage, schema, indexname)
