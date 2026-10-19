from __future__ import annotations

import ipaddress
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Iterable, List
from urllib.parse import urlsplit, urlunsplit

HOST_RE = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
MAX_URL = 2000
MAX_ALLOW = 20
MAX_SITES = 200
SAFE_NON_HOST_SCHEMES = {"data", "blob", "about", "qrc", "chrome-error"}   # внутренние схемы без обращения в сеть
NETWORK_SCHEMES = {"https", "wss"}
PRIVATE_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".home", ".corp", ".intranet",
                    ".home.arpa", ".test", ".invalid", ".example", ".onion")

PUBLIC_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au", "org.au", "co.jp", "co.in", "co.nz",
    "com.br", "com.cn", "com.tr", "com.ua", "co.za", "com.mx", "com.ar",
    "github.io", "gitlab.io", "pages.dev", "workers.dev", "herokuapp.com", "blogspot.com", "vercel.app",
    "netlify.app", "web.app", "firebaseapp.com", "appspot.com", "cloudfront.net", "amazonaws.com",
    "azurewebsites.net", "fly.dev", "onrender.com", "wordpress.com", "tumblr.com", "weebly.com",
}

NEVER_ALLOW = {
    "doubleclick.net", "googlesyndication.com", "googleadservices.com", "googletagmanager.com",
    "googletagservices.com", "google-analytics.com", "adservice.google.com", "analytics.google.com",
    "facebook.net", "scorecardresearch.com", "adnxs.com", "taboola.com", "outbrain.com", "criteo.com",
    "criteo.net", "hotjar.com", "mixpanel.com", "segment.io", "amplitude.com", "mc.yandex.ru",
    "an.yandex.ru", "yandexadexchange.net", "counter.yadro.ru", "top-fwz1.mail.ru", "pubmatic.com",
    "rubiconproject.com", "openx.net", "adsrvr.org", "quantserve.com", "moatads.com", "clarity.ms",
}


class SiteError(Exception):
    """Сообщение написано для пользователя."""


def normalize_host(host: str) -> str:
    host = host.strip().rstrip(".").lower()
    if not host:
        raise SiteError("В адресе нет имени сайта")
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        raise SiteError("Имя сайта содержит недопустимые символы")


def is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def is_private_host(host: str) -> bool:
    """Локальные и служебные адреса: домашний роутер, intranet, localhost, имена без точки."""
    h = host.strip("[]").lower().rstrip(".")
    if is_ip(h):
        return not ipaddress.ip_address(h).is_global
    if "." not in h or h == "localhost":
        return True
    return any(h == s[1:] or h.endswith(s) for s in PRIVATE_SUFFIXES)


def host_matches(host: str, domain: str) -> bool:
    host, domain = host.lower().rstrip("."), domain.lower().rstrip(".")
    return host == domain or host.endswith("." + domain)


def is_tracker(host: str) -> bool:
    return any(host_matches(host, d) for d in NEVER_ALLOW)


def validate_domain(text: str) -> str:
    d = normalize_host(text.strip().lstrip("*.").lstrip("."))
    if is_ip(d):
        raise SiteError(f"«{text}»: IP-адреса разрешать нельзя")
    if not HOST_RE.match(d):
        raise SiteError(f"«{text}» не похоже на домен (пример: example.com)")
    if d in PUBLIC_SUFFIXES:
        raise SiteError(f"«{d}» — общий хостинг: разрешите конкретный поддомен, например user.{d}")
    if is_private_host(d):
        raise SiteError(f"«{d}» — локальный адрес, доступ к нему закрыт")
    if is_tracker(d):
        raise SiteError(f"«{d}» — рекламный или аналитический домен, он блокируется всегда")
    return d


def parse_allow(raw) -> List[str]:
    if isinstance(raw, str):
        raw = re.split(r"[,\s;]+", raw)
    if not isinstance(raw, (list, tuple)):
        raise SiteError("Список доменов задан неверно")
    out: List[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise SiteError("Домены должны быть строками")
        if item.strip():
            d = validate_domain(item)
            if d not in out:
                out.append(d)
    if len(out) > MAX_ALLOW:
        raise SiteError(f"Слишком много доменов (максимум {MAX_ALLOW})")
    return out


@dataclass
class Parsed:
    url: str
    host: str
    warnings: List[str] = field(default_factory=list)


def parse_url(text: str) -> Parsed:
    text = (text or "").strip()
    if not text:
        raise SiteError("Введите адрес сайта")
    if len(text) > MAX_URL:
        raise SiteError("Адрес слишком длинный")
    if "\\" in text or any(ord(c) < 32 or c.isspace() for c in text):
        raise SiteError("В адресе есть пробелы или недопустимые символы")
    warnings: List[str] = []
    if "://" not in text:
        text = "https://" + text
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError:
        raise SiteError("Адрес не удалось разобрать")
    scheme = parts.scheme.lower()
    if scheme == "http":
        scheme = "https"
        warnings.append("Адрес был http:// — открывается только по защищённому https://")
    elif scheme != "https":
        raise SiteError("Разрешены только адреса https:// (схемы file:, javascript:, data: и другие закрыты)")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise SiteError("Логин или пароль в адресе запрещены: так маскируют поддельные сайты")
    if port not in (None, 443):
        raise SiteError("Нестандартные порты закрыты: используйте обычный адрес без :порт")
    original_host = parts.hostname or ""
    host = normalize_host(original_host)
    if is_ip(host):
        raise SiteError("Сайты по IP-адресу не поддерживаются: используйте доменное имя")
    if not HOST_RE.match(host):
        raise SiteError("Это не похоже на адрес сайта (пример: example.com)")
    if is_private_host(host):
        raise SiteError("Локальные адреса закрыты: из этого окна нельзя обращаться к домашней сети и роутеру")
    if any(ord(c) > 127 for c in original_host) or "xn--" in host:
        warnings.append(f"Имя сайта записано необычными символами, фактический адрес: {host}. "
                        "Проверьте, что это именно тот сайт, который вам нужен")
    url = urlunsplit(("https", host, parts.path or "/", parts.query, ""))
    return Parsed(url=url, host=host, warnings=warnings)


@dataclass(frozen=True)
class Decision:
    ok: bool
    reason: str = ""          # "", scheme, empty, ip, private, tracker, ping, not_allowed


def decide(scheme: str, host: str, allow: Iterable[str], resource: str = "other") -> Decision:
    """Единственное место, где решается судьба запроса. Используется и для навигации, и для подресурсов."""
    scheme, host = scheme.lower(), host.lower().rstrip(".")
    if scheme in SAFE_NON_HOST_SCHEMES:
        return Decision(True)
    if scheme not in NETWORK_SCHEMES:
        return Decision(False, "scheme")
    if not host:
        return Decision(False, "empty")
    if is_ip(host):
        return Decision(False, "ip")
    if is_private_host(host):
        return Decision(False, "private")
    if is_tracker(host):
        return Decision(False, "tracker")
    if resource == "ping":
        return Decision(False, "ping")
    if any(host_matches(host, d) for d in allow):
        return Decision(True)
    return Decision(False, "not_allowed")


REASONS = {"scheme": "небезопасная схема", "empty": "пустой адрес", "ip": "IP-адрес", "private": "локальный адрес",
           "tracker": "реклама или аналитика", "ping": "фоновая отправка данных", "not_allowed": "домен не разрешён"}
HARD_BLOCK = {"scheme", "empty", "ip", "private", "tracker"}


@dataclass
class Site:
    id: str
    name: str
    url: str
    allow: List[str] = field(default_factory=list)       
    js: bool = True
    persist: bool = False
    fullscreen: bool = True
    description: str = ""
    source: str = ""
    added: float = 0.0

    @property
    def host(self) -> str:
        return urlsplit(self.url).hostname or ""

    def effective_allow(self) -> frozenset:
        d = {self.host, *self.allow}
        if self.host.startswith("www."):
            d.add(self.host[4:])
        return frozenset(x for x in d if x)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "url": self.url, "allow": list(self.allow), "js": self.js,
                "persist": self.persist, "fullscreen": self.fullscreen, "description": self.description,
                "source": self.source, "added": self.added}


def new_site_id() -> str:
    return "s" + secrets.token_hex(5)


def _bool(obj: dict, key: str, default: bool) -> bool:
    v = obj.get(key, default)
    if not isinstance(v, bool):
        raise SiteError(f"Параметр «{key}» должен быть true или false")
    return v


def _label(v, limit: int, what: str, required: bool = True) -> str:
    if v is None and not required:
        return ""
    if not isinstance(v, str):
        raise SiteError(f"Поле «{what}» должно быть строкой")
    v = " ".join(v.split())
    if required and not v:
        raise SiteError(f"Поле «{what}» не заполнено")
    if len(v) > limit:
        raise SiteError(f"Поле «{what}» длиннее {limit} символов")
    return v


def parse_site(obj, *, keep_id: bool = True) -> Site:
    """Разбор описания сайта: из файла-расширения или из хранилища. Всё проверяется заново."""
    if not isinstance(obj, dict):
        raise SiteError("Описание сайта должно быть объектом JSON")
    sid = obj.get("id")
    if not keep_id or sid is None:
        sid = new_site_id()
    if not isinstance(sid, str) or not ID_RE.match(sid):
        raise SiteError("id сайта: латиница в нижнем регистре, цифры, «-» и «_», до 40 символов")
    perms = obj.get("permissions", obj)
    if not isinstance(perms, dict):
        raise SiteError("Блок permissions задан неверно")
    parsed = parse_url(obj.get("url", ""))
    allow = parse_allow(obj.get("allow", []))
    added = obj.get("added", 0.0)
    return Site(id=sid, name=_label(obj.get("name"), 40, "name"), url=parsed.url, allow=allow,
                js=_bool(perms, "js", True), persist=_bool(perms, "persist", False),
                fullscreen=_bool(perms, "fullscreen", True),
                description=_label(obj.get("description"), 160, "description", required=False),
                source=_label(obj.get("source"), 40, "source", required=False),
                added=float(added) if isinstance(added, (int, float)) and not isinstance(added, bool) else 0.0)


def describe_permissions(site: Site) -> List[str]:
    """Что получает сайт — для окна подтверждения при подключении."""
    lines = [f"Открывается только: {site.host}"]
    if site.allow:
        lines.append("Дополнительно разрешены домены: " + ", ".join(site.allow))
    lines.append("JavaScript: " + ("включён" if site.js else "выключен (многие сайты будут неполными)"))
    lines.append("Вход в аккаунт: " + ("запоминается на диске (файлы сеанса не шифруются)" if site.persist
                                       else "не запоминается: после закрытия всё забывается"))
    lines.append("Полный экран: " + ("разрешён" if site.fullscreen else "запрещён"))
    lines.append("Всегда запрещены: камера и микрофон, геолокация, уведомления, загрузка файлов, "
                 "всплывающие окна, доступ к буферу обмена, переходы на другие сайты")
    return lines


def connect(manifest: Site) -> Site:
    """Подключение сайта из каталога: свежая копия под новым id; права берутся ровно такие, какие показаны в подтверждении."""
    return Site(id=new_site_id(), name=manifest.name, url=manifest.url, allow=list(manifest.allow), js=manifest.js,
                persist=manifest.persist, fullscreen=manifest.fullscreen, description=manifest.description,
                source=manifest.id, added=time.time())


def new_site(name: str, url: str, allow=(), **perms) -> Site:
    p = parse_url(url)
    return Site(id=new_site_id(), name=_label(name, 40, "name"), url=p.url, allow=parse_allow(list(allow)),
                js=perms.get("js", True), persist=perms.get("persist", False),
                fullscreen=perms.get("fullscreen", True), added=time.time())
