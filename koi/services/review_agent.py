"""Paper review agent — compatibility entry for koi.review_agent."""
import sys

from koi.services import review as _module

sys.modules[__name__] = _module
