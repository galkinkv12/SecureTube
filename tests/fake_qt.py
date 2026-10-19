import sys, types


class _Meta(type):
    def __getattr__(cls, n):
        if n.startswith("__"):
            raise AttributeError(n)
        return _Any()


class _Any(metaclass=_Meta):
    def __init__(self, *a, **k): pass
    def __getattr__(self, n):
        if n.startswith("__"):
            raise AttributeError(n)
        return _Any()
    def __call__(self, *a, **k): return _Any()
    def __iter__(self): return iter(())
    def __int__(self): return 0
    def __index__(self): return 0
    def __float__(self): return 0.0
    def __lt__(self, o): return False
    __gt__ = __le__ = __ge__ = __lt__
    def _op(self, *a): return _Any()
    __add__ = __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = __truediv__ = __rtruediv__ = _op
    __floordiv__ = __or__ = __ror__ = __and__ = __rand__ = __neg__ = _op


for _n in ("setChecked", "mousePressEvent", "mouseMoveEvent", "mouseReleaseEvent", "mouseDoubleClickEvent",
           "enterEvent", "leaveEvent", "resizeEvent", "showEvent", "changeEvent", "closeEvent", "paintEvent",
           "wheelEvent", "keyPressEvent", "dragEnterEvent", "dropEvent", "event", "eventFilter", "sizeHint",
           "paint", "data", "rowCount", "setSourceModel", "filterAcceptsRow", "lessThan", "acceptNavigationRequest",
           "createWindow", "javaScriptConsoleMessage", "interceptRequest"):
    setattr(_Any, _n, lambda self, *a, **k: _Any())


class _Index:
    def __init__(self, *a): pass
    def isValid(self): return False
    def row(self): return -1


class _QUrl(_Any):
    """Рабочая мини-версия QUrl: нужны scheme/host/toString."""
    def __init__(self, text=""):
        from urllib.parse import urlsplit
        self._t = text if isinstance(text, str) else ""
        try:
            self._p = urlsplit(self._t)
        except ValueError:
            self._p = urlsplit("")
    def scheme(self): return self._p.scheme
    def host(self): return self._p.hostname or ""
    def toString(self): return self._t
    def isEmpty(self): return not self._t
    @staticmethod
    def fromLocalFile(p): return _QUrl("file://" + str(p))


class _QLineEdit(_Any):
    def __init__(self, text="", *a, **k): self._t = text if isinstance(text, str) else ""
    def text(self): return self._t
    def setText(self, t): self._t = t
    def clear(self): self._t = ""


class _QStackedWidget(_Any):
    def __init__(self, *a, **k): self._w, self._cur = [], None
    def addWidget(self, w):
        self._w.append(w)
        if self._cur is None: self._cur = w
        return len(self._w) - 1
    def setCurrentWidget(self, w): self._cur = w
    def currentWidget(self): return self._cur


class Signal:
    def __init__(self, *a): self.name = None
    def __set_name__(self, owner, name): self.name = name
    def __get__(self, obj, owner=None):
        if obj is None: return self
        return obj.__dict__.setdefault("_sigs", {}).setdefault(self.name, _Bound())


class _Bound:
    def __init__(self): self.slots = []
    def connect(self, f): self.slots.append(f)
    def disconnect(self, *a): self.slots.clear()
    def emit(self, *a):
        for f in list(self.slots):
            if isinstance(f, _Bound): f.emit(*a)
            else:
                try: f(*a)
                except TypeError:
                    f()


def _mod(name):
    m = types.ModuleType(name)
    cache = {}
    def getattr_(n):
        if n.startswith("__"): raise AttributeError(n)
        if n == "Signal": return Signal
        if n == "QModelIndex": return _Index
        if n == "QUrl": return _QUrl
        if n == "QStackedWidget": return _QStackedWidget
        if n == "QLineEdit": return _QLineEdit
        if n not in cache:
            cache[n] = _Meta(n, (_Any,), {})
        return cache[n]
    m.__getattr__ = getattr_
    return m


def install():
    pkg = _mod("PySide6"); sys.modules["PySide6"] = pkg
    for sub in ("QtCore", "QtGui", "QtWidgets", "QtMultimedia", "QtMultimediaWidgets", "QtNetwork", "QtWebEngineCore", "QtWebEngineWidgets"):
        m = _mod("PySide6." + sub); sys.modules["PySide6." + sub] = m; setattr(pkg, sub, m)
