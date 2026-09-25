"""
email_hygiene.py

Riconosce indirizzi email *strutturalmente* inutilizzabili come destinatari di outreach.
Nessuna rete, nessuna dipendenza: solo regole deterministiche.

Uso:
    from email_hygiene import junk_reason
    reason = junk_reason("0613d19f...@sentry.io")   # -> "error_tracking_key"
    if reason: ...                                    # None = indirizzo plausibile

Codici restituiti:
    invalid_syntax        formato non valido
    file_extension        finto indirizzo tipo "logo@2x.png"
    reserved_domain       dominio riservato/di documentazione (RFC 2606: example.*, .test, .invalid ...)
    placeholder_domain    dominio segnaposto usato nei form/esempi (email.com, company.com, musterfirma.de ...)
    error_tracking_key    chiave DSN di Sentry/Bugsnag & co. (32 hex @ host di tracking)
    system_mailbox        noreply / mailer-daemon / postmaster / bounce
    test_fixture_address  indirizzo generato da test (suffisso timestamp, es. ceo_1789853271@...)
"""
from __future__ import annotations

import re
from typing import Optional

_SYNTAX = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)+$")

_FILE_EXT_TLDS = {
    "png", "jpg", "jpeg", "gif", "webp", "svg", "ico", "bmp", "js", "css", "map", "woff", "woff2", "ttf", "pdf",
}

_RESERVED_TLDS = {"test", "example", "invalid", "localhost", "local", "internal"}
_RESERVED_DOMAINS = {"example.com", "example.org", "example.net", "example.edu"}

# Domini segnaposto che compaiono nei form, nei template e nelle pagine di esempio.
_PLACEHOLDER_DOMAINS = {
    "exemple.com", "exemple.fr", "email.com", "company.com", "domain.com", "yourdomain.com",
    "yourcompany.com", "mydomain.com", "mysite.com", "yoursite.com", "test.com", "sample.com",
    "dummy.com", "domain.tld", "email.tld", "site.com", "website.com", "acme.com",
}
# "Muster..." è il segnaposto tedesco (musterfirma.de, musternamegmbh.de, ...): solo i token noti,
# perché "musterhaus.de" & simili sono aziende vere.
_PLACEHOLDER_LABEL = re.compile(
    r"^(musterfirma|musternam|mustergewerbe|mustermann|musterfrau|musterunternehmen|musterstadt|musterag|mustergmbh)"
)

_TRACKING_HOST = re.compile(
    r"(^|[.\-])(sentry|bugsnag|rollbar|raygun|honeybadger|ingest)([.\-]|$)|wixpress\.com$|bug-reporting", re.I
)
_HEX_KEY = re.compile(r"^[0-9a-f]{24,64}$", re.I)

_SYSTEM_LOCALPARTS = {
    "noreply", "no-reply", "no_reply", "donotreply", "do-not-reply", "do_not_reply",
    "mailer-daemon", "postmaster", "bounce", "bounces",
}

# Suffisso "_<timestamp unix>" (10+ cifre, eventuale parte decimale) tipico delle fixture di test
_TEST_SUFFIX = re.compile(r"_\d{9,}(\.\d+)?$")


def junk_reason(email: Optional[str]) -> Optional[str]:
    """Ritorna un codice motivo se l'indirizzo è inutilizzabile, altrimenti None."""
    if not email or not isinstance(email, str):
        return "invalid_syntax"
    e = email.strip().lower()
    if not _SYNTAX.match(e):
        return "invalid_syntax"

    local, domain = e.rsplit("@", 1)
    tld = domain.rsplit(".", 1)[-1]

    if tld in _FILE_EXT_TLDS:
        return "file_extension"
    if domain in _RESERVED_DOMAINS or tld in _RESERVED_TLDS or domain.endswith((".example.com", ".example.org")):
        return "reserved_domain"
    if domain in _PLACEHOLDER_DOMAINS or _PLACEHOLDER_LABEL.match(domain.split(".")[0]):
        return "placeholder_domain"
    if _HEX_KEY.match(local) or _TRACKING_HOST.search(domain):
        return "error_tracking_key"
    if local in _SYSTEM_LOCALPARTS:
        return "system_mailbox"
    if _TEST_SUFFIX.search(local):
        return "test_fixture_address"
    return None


def is_junk(email: Optional[str]) -> bool:
    return junk_reason(email) is not None
