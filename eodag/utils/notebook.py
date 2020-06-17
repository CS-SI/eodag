# -*- coding: utf-8 -*-
# Copyright 2020, CS GROUP - France, http://www.c-s.fr
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


class NotebookWidgets(object):
    """Display / handle ipython widgets"""

    ipython = False
    html_box = None
    html_box_shown = False
    display = None

    def __init__(self):
        try:
            __IPYTHON__
            self.ipython = True

            from ipywidgets import HTML
            from IPython.display import display

            self.display = display

            self.html_box = HTML()

        except NameError:
            pass

    def display_html(self, html_value):
        """Display HTML message"""

        if self.ipython:
            self.html_box.value = html_value

            if not self.html_box_shown:
                self.display(self.html_box)
                self.html_box_shown = True

    def clear_html(self):
        """Clear HTML message"""

        if self.ipython:
            self.html_box.value = ""
