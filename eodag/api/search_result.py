# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved


class SearchResult:

    def __init__(self, products):
        self.__final_result = []
        self.__latest_results = products
        self.__original = products

    def crunch(self, cruncher):
        self.__latest_results = cruncher.proceed(self.__latest_results)
        self.__final_result.extend(self.__latest_results)
        return self

    def crunch_original(self, cruncher):
        pass

    def __len__(self):
        if not self.__final_result:
            return len(self.__original)
        return len(self.__final_result)

    def __nonzero__(self):
        return bool(self.__final_result)

    def __iter__(self):
        return iter(self.__final_result)

    def __repr__(self):
        return repr(self.__final_result)
