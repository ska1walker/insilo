#!/usr/bin/env python3
"""Hält das Referenz-CSS der Bausteine und eine Anwendung gleich.

    python3 werkzeug/bauteile.py pfad/zur/globals.css                 # prüft: Rückgabe 1 bei Abweichung
    python3 werkzeug/bauteile.py pfad/zur/globals.css --uebernehmen   # schreibt bauteile/ aus der App
    python3 werkzeug/bauteile.py pfad/zur/globals.css --einsetzen     # schreibt bauteile/ in die App
    python3 werkzeug/bauteile.py --selbst                             # prüft bauteile/ ohne App
    python3 werkzeug/bauteile.py pfad/zur/globals.css --abschnitte    # zeigt die Abschnitte der App

Die Anwendung kennzeichnet jeden Abschnitt ihres Stylesheets mit einer
Kopfzeile ``/* ── Titel [KENNUNG] ─…``. Alles bis zur nächsten solchen Zeile
gehört zu dieser Kennung. Je Fundament (``AM-``) und Anwendungsbaustein
(``HB-``) gibt es ``bauteile/<KENNUNG>.css`` und ``bauteile/<KENNUNG>.md`` mit
der Liste der Token, die der Baustein liest. ``AM-TOKEN`` ist
``tokens/app.css``; ``RK-`` (Rocket), ``IN-`` (Insilo) und ``RL-`` (Relay)
sind Fachlichkeit der Anwendung und bleiben dort.

**Das CI ist die Quelle** (ABGLEICH.md, Paket 4; Kai, 01.10.2026). Eine App
nimmt die Bausteine aus einem Stand ``ci-YY.M.n`` und prüft sich mit diesem
Skript dagegen. ``--uebernehmen`` ist der eine Weg zurück: Einen in der App
erprobten Baustein schreibt es nach ``bauteile/``, und der Weg geht als PR
hier hinein, bevor die App ihn holt. Eine App ohne die ``.md``-Dateien (ihre
Kopie unter ``frontend/ci/``) ruft das Skript mit ``--ohne-md``.

``--einsetzen`` ist der Weg hin: Es schreibt jeden Baustein des Stands in die
Abschnitte der App, an ihre Stelle und in ihre Schicht. Das Holskript der App
ruft es nach dem Holen auf; so wird ein neuer Stand in jeder App zu einem
Diff, den ihre CI prüft (STAND.md, „Nachziehen“). Was sich nicht eindeutig
einsetzen lässt — ein Baustein, den die App noch nicht hat, eine andere Zahl
von Abschnitten —, meldet es, statt zu raten.
"""
import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent
ZIEL = HIER / "bauteile"
TOKEN = HIER / "tokens" / "app.css"

KOPF = re.compile(r"^\s*/\* ── (.*?)(?:\s*\[((?:AM|HB|RK|IN|RL)-[A-Z]+)\])?\s*[─\s]*(?:\*/)?\s*$")
KOPF_LOSE = re.compile(r"^\s*/\* ── ")
KENNUNG_IM_KOPF = re.compile(r"\[((?:AM|HB|RK|IN|RL)-[A-Z]+)\]")
BANNER = re.compile(r"^\s*/\* ═")
FARBE = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla|oklch|oklab)\(")
VAR = re.compile(r"var\((--am-[a-z0-9-]+)")
TOKEN_NAME = re.compile(r"(--am-[a-z0-9-]+)\s*:")
# AM-TOKEN steht als tokens/app.css im CI. AM-PAKET ist Paketgut, das die
# Anwendung mitführt, aber nicht benutzt (Rocket, docs/MODULE.md „Noch offen“).
NICHT_IM_CI = {"AM-TOKEN", "AM-PAKET"}
GENERIERT = (
    "/* Baustein aus dem AImighty-CI (bauteile/) — Quelle ist das CI.\n"
    "   Eine App trägt den Abschnitt unverändert; geprüft mit werkzeug/bauteile.py. */\n"
)


def code(zeile: str, im_kommentar: bool) -> tuple[str, bool]:
    """Die Zeile ohne Kommentare und Zeichenketten — nur fürs Klammerzählen."""
    aus, i = [], 0
    while i < len(zeile):
        if im_kommentar:
            ende = zeile.find("*/", i)
            if ende < 0:
                return "".join(aus), True
            i, im_kommentar = ende + 2, False
        elif zeile.startswith("/*", i):
            im_kommentar, i = True, i + 2
        elif zeile[i] in "\"'":
            ende = zeile.find(zeile[i], i + 1)
            i = len(zeile) if ende < 0 else ende + 1
        else:
            aus.append(zeile[i])
            i += 1
    return "".join(aus), im_kommentar


def abschnitte(text: str):
    """Liefert (kennung, schicht, zeilen, zeilennummer) je Abschnitt und die Fehler."""
    fehler, ergebnis = [], []
    tiefe, schicht, im_kommentar, im_banner = 0, None, False, False
    aktuell = None  # [kennung, schicht, zeilen, nr]
    token_vorbei = False
    banner: list[str] = []
    for nr, zeile in enumerate(text.splitlines(), 1):
        if im_banner or (not im_kommentar and BANNER.match(zeile)):
            # Ein Banner (/* ═══ … */) trennt große Teile. Trägt es eine
            # Kennung, beginnt mit ihm ein Abschnitt — so beim Token-Block.
            banner.append(zeile)
            im_banner = "*/" not in zeile
            if not im_banner:
                k = KENNUNG_IM_KOPF.search("\n".join(banner))
                banner = []
                if k and tiefe == 0:
                    aktuell = [k.group(1), None, [], nr, False, []]
                    ergebnis.append(aktuell)
                    token_vorbei = token_vorbei or k.group(1) != "AM-TOKEN"
            continue
        if not im_kommentar and KOPF_LOSE.match(zeile):
            k = KENNUNG_IM_KOPF.search(zeile)
            if k:
                kennung = k.group(1)
                if kennung != "AM-TOKEN":
                    token_vorbei = True
                if tiefe != (1 if schicht else 0):
                    fehler.append(f"Zeile {nr}: [{kennung}] beginnt mitten in einem Block")
                aktuell = [kennung, schicht, [], nr, False, []]
                ergebnis.append(aktuell)
            elif token_vorbei:
                fehler.append(f"Zeile {nr}: Abschnittskopf ohne Kennung")
        c, im_kommentar_danach = code(zeile, im_kommentar)
        m = re.match(r"^@layer\s+([a-z-]+)\s*\{\s*$", c.strip())
        if tiefe == 0 and m:
            schicht, tiefe, im_kommentar = m.group(1), 1, im_kommentar_danach
            if aktuell and not aktuell[4]:
                aktuell[1] = schicht
            continue
        neu = tiefe + c.count("{") - c.count("}")
        if schicht and neu == 0 and c.strip() == "}":
            schicht, tiefe, im_kommentar = None, 0, im_kommentar_danach
            continue
        tiefe, im_kommentar = neu, im_kommentar_danach
        if aktuell is not None:
            if c.strip():
                if aktuell[4] and schicht != aktuell[1]:
                    fehler.append(f"Zeile {nr}: [{aktuell[0]}] wechselt die Schicht ohne neuen Kopf")
                aktuell[4] = True
            aktuell[2].append(zeile)
            aktuell[5].append(nr)
        elif aktuell is None and c.strip() and not zeile.startswith("@import") and not zeile.startswith("@config"):
            fehler.append(f"Zeile {nr}: Regel vor dem ersten Abschnitt")
    for a in ergebnis:
        while a[2] and not a[2][-1].strip():
            a[2].pop()
            a[5].pop()
        t = 0
        im = False
        for z in a[2]:
            c, im = code(z, im)
            t += c.count("{") - c.count("}")
        if t:
            fehler.append(f"Zeile {a[3]}: [{a[0]}] schließt seine Klammern nicht ({t:+d})")
    return ergebnis, fehler


def css_je_kennung(ergebnis, quelle: str) -> dict[str, str]:
    teile: dict[str, list[str]] = {}
    for kennung, schicht, zeilen, *_ in ergebnis:
        if not kennung.startswith(("AM-", "HB-")) or kennung in NICHT_IM_CI or not zeilen:
            continue
        if schicht:
            # Der Kopf des Abschnitts steht vor der Schicht, nicht in ihr.
            i, im = 0, False
            while i < len(zeilen):
                c, im = code(zeilen[i], im)
                if c.strip():
                    break
                i += 1
            vor = "\n".join(zeilen[:i])
            block = (vor + "\n" if vor else "") + f"@layer {schicht} {{\n" + "\n".join(zeilen[i:]) + "\n}"
        else:
            block = "\n".join(zeilen)
        teile.setdefault(kennung, []).append(block)
    return {k: GENERIERT.format(quelle=quelle) + "\n" + "\n\n".join(v) + "\n" for k, v in teile.items()}


def token_block(css: str) -> str:
    namen = sorted(set(VAR.findall(css)))
    zeilen = ["<!-- token:anfang — gerechnet von werkzeug/bauteile.py, nicht von Hand -->"]
    zeilen += [f"`{n}`" + (" ·" if i < len(namen) - 1 else "") for i, n in enumerate(namen)] or ["(keine)"]
    zeilen.append("<!-- token:ende -->")
    return "\n".join(zeilen)


def md_mit_token(md: str, css: str) -> str:
    return re.sub(r"<!-- token:anfang.*?<!-- token:ende -->", lambda _: token_block(css), md, flags=re.DOTALL)


def bausteine_im_ci() -> dict[str, str]:
    return {d.stem: d.read_text() for d in sorted(ZIEL.glob("*.css"))}


def befunde_css(soll: dict[str, str]) -> list[str]:
    fehler = []
    bekannt = set(TOKEN_NAME.findall(TOKEN.read_text()))
    for kennung, css in sorted(soll.items()):
        ohne_bilder = re.sub(r"url\(\"?data:[^)]*\)", "", re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL))
        if FARBE.search(ohne_bilder):
            fehler.append(f"{kennung}: Farbwert statt Token ({FARBE.search(ohne_bilder).group(0)})")
        for n in sorted(set(VAR.findall(ohne_bilder)) - bekannt):
            fehler.append(f"{kennung}: {n} steht nicht in tokens/app.css")
    return fehler


def befunde_md(soll: dict[str, str], schreiben: bool) -> list[str]:
    fehler = []
    for md in sorted(ZIEL.glob("[AH][MB]-*.md")):
        text = md.read_text()
        verweis = re.search(r"<!-- css: ((?:AM|HB)-[A-Z]+|keins) -->", text)
        quelle_css = verweis.group(1) if verweis else md.stem
        if quelle_css == "keins":
            continue
        if quelle_css not in soll:
            fehler.append(f"bauteile/{md.name}: kein CSS zu [{quelle_css}]")
            continue
        if "<!-- token:anfang" not in text:
            fehler.append(f"bauteile/{md.name}: Token-Block fehlt")
            continue
        neu = md_mit_token(text, soll[quelle_css])
        if neu != text:
            if schreiben:
                md.write_text(neu)
            else:
                fehler.append(f"bauteile/{md.name}: Token-Liste veraltet")
    for kennung in sorted(soll):
        if not (ZIEL / f"{kennung}.md").exists():
            fehler.append(f"bauteile/{kennung}.md fehlt")
    return fehler


def _ohne_code(zeilen: list[str]) -> int:
    """Wie viele Zeilen am Anfang nur Kommentar oder leer sind."""
    im, n = False, 0
    for z in zeilen:
        c, im = code(z, im)
        if c.strip():
            break
        n += 1
    return n


TOKEN_ANFANG = ":root {"
TOKEN_ENDE = 'html[data-dichte="kompakt"]'


def token_einsetzen(text: str) -> tuple[str, list[str]]:
    """Ersetzt den Token-Block der App durch tokens/app.css — von „:root {“
    bis zur Zeile mit der Dichte „kompakt“, wie ihn die Apps prüfen."""
    quelle = TOKEN.read_text()
    a, e = text.find(TOKEN_ANFANG), text.find(TOKEN_ENDE)
    if a < 0 or e < 0 or quelle.find(TOKEN_ANFANG) < 0:
        return text, ["Token-Block der App nicht gefunden — von Hand einsetzen"]
    e = text.find("\n", e) + 1 or len(text)
    return text[:a] + quelle[quelle.find(TOKEN_ANFANG):].rstrip("\n") + "\n" + text[e:], []


def einsetzen(text: str) -> tuple[str, list[str], list[str]]:
    """Schreibt Token und Bausteine aus dem CI in die App.

    Liefert den neuen Text, die Befunde (von Hand zu lösen) und Hinweise.
    """
    hinweise: list[str] = []
    text, fehler = token_einsetzen(text)
    app, f = abschnitte(text)
    if f:
        return text, fehler + f, hinweise
    in_app: dict[str, list] = {}
    for a in app:
        if a[0].startswith(("AM-", "HB-")) and a[0] not in NICHT_IM_CI and a[2]:
            in_app.setdefault(a[0], []).append(a)
    ersetzen: list[tuple[int, int, list[str]]] = []  # (erste, letzte, neue Zeilen), 1-basiert
    for kennung, css in sorted(bausteine_im_ci().items()):
        ci, f = abschnitte(css)
        fehler += [f"bauteile/{kennung}.css: {x}" for x in f]
        ci = [b for b in ci if b[0] == kennung and b[2]]
        hier = in_app.get(kennung, [])
        if not hier:
            # Nicht jede App trägt jeden Baustein (Insilo hat kein Board).
            # Ein neuer, den sie braucht, kommt von Hand an seinen Ort.
            hinweise.append(f"[{kennung}] trägt die App nicht — übersprungen")
            continue
        if len(hier) != len(ci):
            fehler.append(f"[{kennung}]: {len(hier)} Abschnitt(e) in der App, {len(ci)} im CI — von Hand einsetzen")
            continue
        for alt, neu in zip(hier, ci):
            if alt[1] != neu[1]:
                fehler.append(f"Zeile {alt[3]}: [{kennung}] steht in Schicht {alt[1] or '-'}, im CI in {neu[1] or '-'}")
                continue
            nrs = alt[5]
            laeufe = [[nrs[0]]]
            for n in nrs[1:]:
                if n == laeufe[-1][-1] + 1:
                    laeufe[-1].append(n)
                else:
                    laeufe.append([n])
            if len(laeufe) == 1:
                ersetzen.append((nrs[0], nrs[-1], neu[2]))
            elif (len(laeufe) == 2 and _ohne_code(alt[2]) >= len(laeufe[0])
                  and _ohne_code(neu[2]) >= len(laeufe[0])):
                # Der Kopf steht vor der Schicht, der Rest in ihr. Wie viele
                # Kommentarzeilen davor stehen, bestimmt die App (im CI stehen
                # alle führenden Kommentare vor @layer — gleich gerechnet).
                k = len(laeufe[0])
                ersetzen.append((laeufe[0][0], laeufe[0][-1], neu[2][:k]))
                ersetzen.append((laeufe[1][0], laeufe[1][-1], neu[2][k:]))
            else:
                fehler.append(f"Zeile {alt[3]}: [{kennung}] ist in der App zerteilt — von Hand einsetzen")
    zeilen = text.split("\n")
    for erste, letzte, neu in sorted(ersetzen, reverse=True):
        zeilen[erste - 1:letzte] = neu
    return "\n".join(zeilen), fehler, hinweise


def main() -> int:
    argumente = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--selbst" in sys.argv:
        soll = bausteine_im_ci()
        fehler = befunde_css(soll) + befunde_md(soll, schreiben=False)
        for f in fehler:
            print(f)
        if fehler:
            print(f"{len(fehler)} Befund(e)")
            return 1
        print(f"{len(soll)} Bausteine, in sich stimmig")
        return 0
    if not argumente:
        print(__doc__)
        return 2
    ergebnis, fehler = abschnitte(Path(argumente[0]).read_text())
    if "--abschnitte" in sys.argv:
        for kennung, schicht, zeilen, nr, *_ in ergebnis:
            print(f"{nr:5} {kennung:18} {schicht or '-':11} {len(zeilen)} Zeilen")
        for f in fehler:
            print("FEHLER", f)
        return 1 if fehler else 0
    if "--einsetzen" in sys.argv:
        pfad = Path(argumente[0])
        neu, befunde, hinweise = einsetzen(pfad.read_text())
        if neu != pfad.read_text():
            pfad.write_text(neu)
        for h in hinweise:
            print(h)
        ergebnis, fehler = abschnitte(neu)
        fehler = befunde + fehler
    uebernehmen = "--uebernehmen" in sys.argv
    soll = css_je_kennung(ergebnis, "")
    fehler += befunde_css(soll)
    if uebernehmen:
        ZIEL.mkdir(exist_ok=True)
        for kennung, css in soll.items():
            (ZIEL / f"{kennung}.css").write_text(css)
    vorhanden = bausteine_im_ci()
    for kennung, css in sorted(soll.items()):
        if vorhanden.get(kennung) != css:
            fehler.append(f"[{kennung}] in der App weicht von bauteile/{kennung}.css ab")
    for kennung in sorted(set(vorhanden) - set(soll)):
        fehler.append(f"bauteile/{kennung}.css: die App hat keinen Abschnitt [{kennung}]")
    if "--ohne-md" not in sys.argv:
        fehler += befunde_md(soll, schreiben=uebernehmen)
    for f in fehler:
        print(f)
    if fehler:
        print(f"{len(fehler)} Befund(e)")
        return 1
    print(f"{len(soll)} Bausteine, gleich mit dem CI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
