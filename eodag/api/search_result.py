# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved


class SearchResult:

    def __init__(self, products):
        self.__final_result = []
        self.__latest_results = products
        self.__original = products
        self.__crunch_calls_count = 0

    def crunch(self, cruncher):
        self.__latest_results = cruncher.proceed(self.__latest_results)
        self.__final_result.extend(self.__latest_results)
        self.__crunch_calls_count += 1
        return self

    def __len__(self):
        return self.__speculate_on_result(len)

    def __nonzero__(self):
        return self.__speculate_on_result(bool)

    def __iter__(self):
        return self.__speculate_on_result(iter)

    def __repr__(self):
        return self.__speculate_on_result(repr)

    def __speculate_on_result(self, func):
        if self.__crunch_calls_count == 0 and not self.__final_result:
            return func(self.__original)
        return func(self.__final_result)
