# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
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


from typing import Any


def check_ipython():
    """Check if called from ipython"""
    try:
        __IPYTHON__
        return True
    except NameError:
        return False


def check_notebook():
    """Check if called from a notebook"""
    try:
        shell = get_ipython().__class__.__name__
        if shell == "ZMQInteractiveShell":
            return True  # Jupyter notebook or qtconsole
        elif shell == "TerminalInteractiveShell":
            return False  # Terminal running IPython
        else:
            return False  # Other type
    except NameError:
        return False  # Probably standard Python interpreter


class NotebookWidgets(object):
    """Display / handle ipython widgets"""

    is_notebook = False
    html_box: Any = None
    html_box_shown = False
    display: Any = None

    def __init__(self):
        self.is_notebook = check_notebook()

        if self.is_notebook:
            from IPython.display import HTML, display, update_display

            self.display = display
            self._update_display = update_display
            self.html_box = HTML()
        else:
            pass

    def display_html(self, html_value):
        """Display HTML message"""

        if self.is_notebook:
            self.html_box.data = html_value

            if not self.html_box_shown:
                self._html_handle = self.display(self.html_box, display_id=True)
                self.html_box_shown = True
            else:
                self._update_display(
                    self.html_box, display_id=self._html_handle.display_id
                )

    def clear_html(self):
        """Clear HTML message"""

        if self.is_notebook:
            self.html_box.data = ""
            self._update_display(self.html_box, display_id=self._html_handle.display_id)
