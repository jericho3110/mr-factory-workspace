"""Work with the AdsPower desktop app: open it; look up groups, tags,
profiles, and proxies; open, create, and re-proxy profiles. Start with
`AdsPower`; see client.py."""

from importlib.metadata import PackageNotFoundError, version

from .api import LocalApi
from .client import AdsPower
from .errors import (
    AdsPowerApiError,
    AdsPowerError,
    AdsPowerNotRunning,
    AmbiguousProfile,
    ConfigError,
    GroupNotFound,
    NotFound,
    ProfileNotFound,
    ProxyNotFound,
    TagNotFound,
)
from .launcher import adspower_candidates, find_adspower, open_adspower, open_app
from .models import Group, OpenedBrowser, Profile, Proxy, Tag

# The version is written in exactly one place, pyproject.toml. pip copies
# it into the installed metadata, and this reads it back from there, so
# the two can never disagree. (See docs/MODULES_AND_PACKAGES.md §7.)
try:
    __version__ = version("mrfactory-adspower")
except PackageNotFoundError:  # running straight from src/ without installing (e.g. the tests)
    __version__ = "0+unknown"

__all__ = [
    "__version__",
    "AdsPower",
    "LocalApi",
    "Group",
    "Tag",
    "Profile",
    "Proxy",
    "OpenedBrowser",
    "AdsPowerError",
    "AdsPowerNotRunning",
    "AdsPowerApiError",
    "ConfigError",
    "NotFound",
    "GroupNotFound",
    "TagNotFound",
    "ProfileNotFound",
    "ProxyNotFound",
    "AmbiguousProfile",
    "adspower_candidates",
    "find_adspower",
    "open_adspower",
    "open_app",
]
