"""The `adspower` command. Run `adspower --help` (or
`adspower <command> --help`) for usage.

The CLI only turns command-line arguments into calls on `AdsPower` and
the results into text; all the actual work is in client.py, so
everything here can also be done from Python. It's split by job:

    app.py       entry point: parser, run one command, safe exit
    commands.py  one cmd_* function per subcommand
    prompts.py   asking the user: pick from a list, confirm, is anyone there?
    output.py    tables and JSON
"""

from .app import build_parser, main

__all__ = ["build_parser", "main"]
