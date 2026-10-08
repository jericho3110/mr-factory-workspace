"""gitship: check, scan, commit, push, publish and release, safely and the same way every time.

Read the modules in this order (pure first, I/O last):

    commitmsg.py  is this a good commit message? (pure)
    scan.py       does anything staged look like a secret or personal data? (pure)
    config.py     the repo's .gitship.json: which checks to run (reads one file)
    runner.py     the one place that starts other programs (git, gh, checks)
    git.py        small typed wrapper around the git commands we need
    layout.py     which repository does this folder belong to?
    workflow.py   ship / publish: the step-by-step flows with their safety gates
    release.py    plan, publish and verify a GitHub release
    cli.py        the `gitship` command
"""

__version__ = "0.1.0"
