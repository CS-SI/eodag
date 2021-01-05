---
name: Bug report
about: Create a report to help us improve
title: ''
labels: bug
assignees: ''

---

**Describe the bug**
A clear and concise description of what the bug is.

**Code To Reproduce**
CLI commands or Python code snippet to reproduce the bug. Please use maximum verbosity using:
```sh
eodag -vvv [OPTIONS] COMMAND [ARGS]...
```
or
```py
from eodag.utils.logging import setup_logging
setup_logging(verbose=3)
```

**Output**
Compete output obtained with maximal verbosity.

**Environment:**
 - Python version: `python --version`
 - EODAG version: `eodag version`

**Additional context**
Add any other context about the bug here.
