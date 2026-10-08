"""Lets the package run as a command: python -m mrfactory.gitship"""

import sys

from .cli import main

sys.exit(main())
