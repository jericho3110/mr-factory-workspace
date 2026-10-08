"""Work with the AdsPower desktop app: open it; look up groups, tags,
profiles, and proxies; open, create (one or many), and re-proxy
profiles; check that a profile's proxy works. Start with `AdsPower`;
see client.py, batch.py, proxycheck.py."""

from importlib.metadata import PackageNotFoundError, version

from .api import LocalApi
from .batch import (
    Batch,
    BatchCreator,
    BatchSettings,
    Created,
    NameIndex,
    Outcome,
    Planned,
    PlanStatus,
    free_proxies,
    name_key,
    plan,
    results_text,
    summarize,
)
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
from .proxycheck import CHECK_URL, ProxyCheck, ProxyCheckUnavailable, check_browser, error_code, parse_ip

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
    # many profiles at once (batch.py)
    "Batch",
    "BatchCreator",
    "BatchSettings",
    "Created",
    "NameIndex",
    "Outcome",
    "Planned",
    "PlanStatus",
    "free_proxies",
    "name_key",
    "plan",
    "results_text",
    "summarize",
    # proxy health (proxycheck.py)
    "CHECK_URL",
    "ProxyCheck",
    "ProxyCheckUnavailable",
    "check_browser",
    "error_code",
    "parse_ip",
]
