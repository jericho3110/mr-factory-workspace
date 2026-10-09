"""devtools: the checks every project runs, written once.

    files.py     which files belong to the project (git's view: tracked + new, minus ignored)
    config.py    the project's .devtools.json
    codescan.py  dangerous code patterns per language (pure)
    security.py  codescan + gitship's file scan (secrets, personal data, never-commit files)
    links.py     Markdown links: local files must exist, web links must load
    cli.py       the `devtools` command
"""

__version__ = "0.1.0"
