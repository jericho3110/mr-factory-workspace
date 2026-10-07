"""Lets the package run as a command: python -m mrfactory.adspower"""

import sys

from .cli import main

sys.exit(main())
