"""Paper review agent — layered implementation."""

from koi.services.review import (
    analysis,
    arxiv,
    artifacts,
    models,
    papers,
    pipeline,
    storage,
    util,
)

_SUBMODULES = (analysis, arxiv, artifacts, models, papers, pipeline, storage, util)

for _mod in _SUBMODULES:
    for _name in dir(_mod):
        if _name.startswith("__"):
            continue
        globals()[_name] = getattr(_mod, _name)

del _mod, _name, _SUBMODULES
