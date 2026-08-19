"""Was verlässt diese Box?

Insilo verspricht, dass Audio, Transkript und Suchindex die Box nicht
verlassen. Das Versprechen hängt aber an der Konfiguration: Der
LLM-Endpunkt ist frei einstellbar, und Webhooks schicken
Zusammenfassungen bewusst nach außen. Ein pauschales "0 Byte" wäre in
vielen Installationen schlicht falsch.

Dieses Modul beantwortet die Frage aus dem, was messbar ist — nie aus
einer Annahme. Es rät nicht: wenn ein Ziel nicht eindeutig als
box-intern erkennbar ist, gilt es als extern. Lieber ein Hinweis zu
viel als ein falsches Entwarnungssignal.
"""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

# Namensräume, die den Cluster nicht verlassen.
#
# Kubernetes löst Dienste im selben Namespace über den kurzen Namen auf
# ("insilo-whisper"), über den Namespace-Pfad ("litellm-kai.svc") oder
# vollqualifiziert (".svc.cluster.local"). Alle drei Formen bleiben im
# Cluster. Die Olares-LiteLLM liegt in einem Nachbar-Namespace, wird aber
# ebenfalls clusterintern adressiert.
_INTERNE_SUFFIXE = (
    ".svc.cluster.local",
    ".svc",
    ".local",
    ".internal",
)

_INTERNE_NAMEN = (
    "localhost",
)


def ist_boxintern(url: str) -> bool:
    """True, wenn der Aufruf die Box nachweislich nicht verlässt.

    Im Zweifel False. Ein unbekanntes Ziel als intern zu melden wäre der
    teurere Fehler — der Nachweis soll Vertrauen tragen, nicht erzeugen.
    """
    if not url or not url.strip():
        # Kein Ziel konfiguriert heißt: es gibt nichts, was hinausgeht.
        return True

    host = urlsplit(url.strip()).hostname
    if not host:
        return False

    host = host.lower().rstrip(".")

    if host in _INTERNE_NAMEN:
        return True

    # Loopback und private Netze (RFC 1918) verlassen die Box bzw. das
    # Kundennetz nicht. Link-local zählt ebenfalls dazu.
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback or ip.is_private or ip.is_link_local
    except ValueError:
        pass  # kein IP-Literal, weiter als Hostname prüfen

    if host.endswith(_INTERNE_SUFFIXE):
        return True

    # Ein Name ohne Punkt ist ein Kubernetes-Dienst im eigenen Namespace
    # ("insilo-whisper", "litellm-svc"). Öffentliche Ziele tragen immer
    # eine Domain.
    if "." not in host:
        return True

    return False


def ist_eigene_zone(url: str, zone: str | None = None) -> bool:
    """True, wenn das Ziel die eigene Box unter ihrer öffentlichen Adresse ist.

    Olares reicht die Zone als `OLARES_ZONE` in jeden Pod (etwa
    "kaivostudio.olares.de"). Zeigt ein Ziel dorthin, läuft es auf
    derselben Maschine — der Aufruf nimmt zwar den Weg über DNS und den
    Tunnel nach draußen, landet aber wieder hier.

    Das ist der praktisch häufigste Fall: Der Envoy-Sidecar vor
    Nachbar-Apps wie LiteLLM verlangt einen Authelia-Token, den ein
    Server-zu-Server-Aufruf nicht hat (geprüft: clusterintern antwortet er
    mit 400 „cannot get user name from header", mit Benutzernamen mit
    401). Die öffentliche Adresse ist deshalb kein Umweg aus Nachlässigkeit,
    sondern der einzige Weg, der funktioniert.

    Für den Nachweis ist der Unterschied wesentlich: „läuft auf der
    eigenen Box" ist etwas anderes als „geht an einen fremden Anbieter",
    und beides in einen Topf zu werfen würde die Aussage entwerten.
    """
    if zone is None:
        zone = os.environ.get("OLARES_ZONE", "")
    zone = (zone or "").strip().lower().rstrip(".")
    if not zone:
        return False

    host = urlsplit((url or "").strip()).hostname
    if not host:
        return False
    host = host.lower().rstrip(".")

    return host == zone or host.endswith("." + zone)


@dataclass(frozen=True)
class ExternesZiel:
    """Ein konfiguriertes Ziel außerhalb der Box."""

    art: str  # "llm" | "webhook"
    host: str
    beschreibung: str


@dataclass(frozen=True)
class EgressLage:
    """Der belegbare Zustand — nichts davon ist geschätzt."""

    llm_extern: bool
    llm_host: str | None
    webhooks_aktiv: int
    ziele: tuple[ExternesZiel, ...]
    gesendete_bytes: int | None  # None = nie etwas zugestellt
    letzter_versand: str | None  # ISO-Zeitstempel

    @property
    def alles_bleibt(self) -> bool:
        return not self.llm_extern and self.webhooks_aktiv == 0
