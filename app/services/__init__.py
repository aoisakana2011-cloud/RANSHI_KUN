# app/services/__init__.py
from .io import *
from .parsing import *
from .aggregation import *
__all__ = []
for m in ("io","parsing","aggregation"):
    try:
        mod = __import__(f"app.services.{m}", fromlist=["*"])
        for name in getattr(mod, "__all__", [n for n in dir(mod) if not n.startswith("_")]):
            globals()[name] = getattr(mod, name)
            __all__.append(name)
    except Exception:
        pass