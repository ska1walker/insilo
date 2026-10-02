#!/usr/bin/env python3
"""Baut den Insilo-Eintrag im Markt (bayerhazard/aimighty-market).

Nach Rockets scripts/markt-eintrag.py (Kai, 2.10.2026: „automatisch wie bei
Rocket"). Unterschied zu Rocket: Insilos Notizen haben Absätze — sie bleiben
erhalten, statt zu einer Zeile zusammengezogen zu werden, wie es im Markt
seit 0.1.81 steht. Was bisher von Hand geschah (Skill olares-release, §6),
an einer Stelle:

- `functions/_apps.ts`: Version des Insilo-Eintrags, vorn in
  `upgradeDescription` die Notizen jeder Version, die der Markt noch nicht
  kennt (`olares/markt/<version>.md`). Kam ein Eintrag nie an, reist seine
  Notiz mit dem nächsten.
- `functions/_apps.ts`: die Kategorien aus `olares/OlaresManifest.yaml`
  (`metadata.categories`) — der Markt zeigt die App dort, wo das Chart sie
  einordnet, und beides kann nicht auseinanderlaufen.
- `functions/_lib.ts`: der Chart-Schlüssel `insilo-<version>.tgz` mit dem
  frisch kodierten Release-Anhang, alte Insilo-Schlüssel entfernt, und
  `CANONICAL_EPOCH_MS` streng über dem Wert auf main.

Aufruf (aus der Action `markt.yml` oder von Hand):

    python3 scripts/markt-eintrag.py --markt <klon> --chart insilo-0.1.103.tgz \
        --version 0.1.103 --notizen olares/markt --pr-text pr.md

Gibt auf stdout den Titel des PR aus. Bricht ab, wenn eine Stelle nicht so
aussieht wie erwartet — lieber kein Eintrag als ein halber.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path


def version_tupel(v: str) -> tuple[int, ...]:
    return tuple(int(t) for t in v.split("."))


def notiz_lesen(datei: Path) -> tuple[str, str, str | None]:
    """`# Titel`, darunter Englisch ab `v<version>: `; optional nach einer Zeile
    `## Deutsch` derselbe Inhalt auf Deutsch, ebenfalls ab `v<version>: `."""
    roh = datei.read_text(encoding="utf-8").strip()
    teile = re.split(r"^## Deutsch\s*$", roh, maxsplit=1, flags=re.MULTILINE)
    zeilen = teile[0].strip().splitlines()
    if not zeilen or not zeilen[0].startswith("# "):
        raise SystemExit(f"{datei}: erste Zeile muss '# <Titel>' sein")
    titel = zeilen[0][2:].strip()
    version = datei.stem
    # Absätze bleiben: eine Leerzeile trennt sie, Zeilen darin rücken zusammen.
    def absaetze(text: str) -> str:
        return "\n\n".join(" ".join(z.strip() for z in a.splitlines()) for a in re.split(r"\n\s*\n", text.strip()) if a.strip())
    en = absaetze("\n".join(zeilen[1:]))
    de = absaetze(teile[1]) if len(teile) > 1 else None
    for sprache, text in (("Englisch", en), ("Deutsch", de)):
        if text is None:
            continue
        if not text.startswith(f"v{version}: "):
            raise SystemExit(f"{datei}: {sprache} muss mit 'v{version}: ' beginnen")
        kein_template(text, datei)
    return titel, en, de


def kein_template(text: str, quelle: Path | str) -> None:
    if "`" in text or "${" in text:
        raise SystemExit(f"{quelle}: kein Backtick und kein '${{' — der Text steht in einem Template-String")


def texte_lesen(datei: Path) -> tuple[str, str]:
    """`# Kurz` (eine Zeile) und `# Beschreibung` (Markdown) für den Markt."""
    roh = datei.read_text(encoding="utf-8")
    m = re.match(r"\s*# Kurz\s*\n(.+?)\n\s*# Beschreibung\s*\n(.+)", roh, flags=re.DOTALL)
    if not m:
        raise SystemExit(f"{datei}: erwartet '# Kurz' und '# Beschreibung'")
    kurz, lang = m.group(1).strip(), m.group(2).strip()
    if "\n" in kurz or '"' in kurz:
        raise SystemExit(f"{datei}: Kurzbeschreibung ist eine Zeile ohne Anführungszeichen")
    kein_template(lang, datei)
    return kurz, lang


FELD = "\n      "  # Einrückung der Felder unter metadata in _apps.ts


def feld_ersetzen(block: str, name: str, wert: str) -> str:
    """Ersetzt ein metadata-Feld samt Wert, gleich in welcher Form es dasteht."""
    m = re.search(re.escape(FELD + name + ":"), block)
    if not m:
        raise SystemExit(f"_apps.ts: {name} im Insilo-Eintrag nicht gefunden")
    n = re.compile(re.escape(FELD) + r"[A-Za-z]+:").search(block, m.end())
    ende = n.start() if n else len(block)
    trenner = "" if wert.startswith("\n") else " "
    return block[: m.start()] + FELD + name + ":" + trenner + wert + "," + block[ende:]


def feld_lesen(block: str, name: str) -> dict[str, str]:
    """Liest einen Text- oder Sprachen-Wert: `...` | "..." | { en: ..., de: ... }."""
    m = re.search(re.escape(FELD + name + ":"), block)
    if not m:
        raise SystemExit(f"_apps.ts: {name} im Insilo-Eintrag nicht gefunden")
    n = re.compile(re.escape(FELD) + r"[A-Za-z]+:").search(block, m.end())
    roh = block[m.end() : n.start() if n else len(block)].strip().rstrip(",").strip()
    def wert(s: str) -> str:
        s = s.strip().rstrip(",").strip()
        if s[:1] == "`":
            return s[1:-1]
        return json.loads(s)
    if roh.startswith("{"):
        paare = re.findall(r'(\w+)\s*:\s*(`[^`]*`|"(?:[^"\\]|\\.)*")', roh)
        return {k: wert(v) for k, v in paare}
    return {"en": wert(roh)}


def sprachen(werte: dict[str, str], als_template: bool) -> str:
    def text(s: str) -> str:
        return f"`{s}`" if als_template else json.dumps(s, ensure_ascii=False)
    zeilen = "".join(f"{FELD}  {k}: {text(s)}," for k, s in werte.items())
    return "{" + zeilen + FELD + "}"


def kategorien_lesen(manifest: Path) -> list[str]:
    """`metadata.categories` aus dem OlaresManifest, ohne YAML-Bibliothek."""
    zeilen = manifest.read_text(encoding="utf-8").splitlines()
    try:
        i = next(n for n, z in enumerate(zeilen) if z.strip() == "categories:")
    except StopIteration:
        raise SystemExit(f"{manifest}: keine categories") from None
    kategorien = []
    for z in zeilen[i + 1 :]:
        s = z.strip()
        if not s.startswith("- "):
            break
        kategorien.append(s[2:].strip().strip("'\""))
    if not kategorien:
        raise SystemExit(f"{manifest}: categories ist leer")
    return kategorien


def app_block(apps: str) -> tuple[int, int]:
    anfang = apps.index('name: "insilo"')
    ende = apps.index("spec: {", anfang)
    return anfang, ende


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--markt", type=Path, required=True)
    a.add_argument("--chart", type=Path, required=True)
    a.add_argument("--version", required=True)
    a.add_argument("--notizen", type=Path, required=True)
    a.add_argument("--pr-text", type=Path)
    a.add_argument("--manifest", type=Path, help="olares/OlaresManifest.yaml — Kategorien von dort")
    a.add_argument("--texte", type=Path, help="Ordner mit beschreibung.en.md und beschreibung.de.md")
    arg = a.parse_args()

    v = arg.version
    apps_datei = arg.markt / "functions" / "_apps.ts"
    lib_datei = arg.markt / "functions" / "_lib.ts"
    apps = apps_datei.read_text(encoding="utf-8")
    lib = lib_datei.read_text(encoding="utf-8")

    # ── _apps.ts ──────────────────────────────────────────────────────────
    anfang, ende = app_block(apps)
    block = apps[anfang:ende]
    m = re.search(r'version: "([0-9.]+)"', block)
    if not m:
        raise SystemExit("_apps.ts: keine Insilo-Version gefunden")
    alt = m.group(1)
    if version_tupel(alt) >= version_tupel(v):
        print(f"Markt hat Insilo {alt}, nichts zu tun für {v}", file=sys.stderr)
        raise SystemExit(3)

    neue = sorted(
        (d for d in arg.notizen.glob("*.md") if re.fullmatch(r"\d+\.\d+\.\d+", d.stem) and version_tupel(alt) < version_tupel(d.stem) <= version_tupel(v)),
        key=lambda d: version_tupel(d.stem),
        reverse=True,
    )
    if not neue or neue[0].stem != v:
        raise SystemExit(f"Notiz {arg.notizen}/{v}.md fehlt")
    notizen = [notiz_lesen(d) for d in neue]
    titel = notizen[0][0]
    neu_en = "\n\n".join(en for _, en, _ in notizen)
    # Eine Version ohne deutsche Notiz steht auch im Deutschen auf Englisch.
    neu_de = "\n\n".join(de or en for _, en, de in notizen)

    block = block.replace(f'version: "{alt}"', f'version: "{v}"', 1)
    if arg.manifest:
        kategorien = kategorien_lesen(arg.manifest)
        block, n = re.subn(
            r"categories: \[[^\]]*\]",
            "categories: [" + ", ".join(f'"{k}"' for k in kategorien) + "]",
            block,
            count=1,
        )
        if n != 1:
            raise SystemExit("_apps.ts: categories im Insilo-Eintrag nicht gefunden")
    bisher = feld_lesen(block, "upgradeDescription")
    upgrade = {"en": neu_en + "\n\n" + bisher["en"]}
    if arg.texte:
        upgrade["de"] = neu_de + "\n\n" + bisher.get("de", bisher["en"])
    elif "de" in bisher:
        upgrade["de"] = neu_en + "\n\n" + bisher["de"]
    block = feld_ersetzen(block, "upgradeDescription", sprachen(upgrade, als_template=True) if len(upgrade) > 1 else f"{FELD}  `{upgrade['en']}`")

    if arg.texte:
        kurz_en, lang_en = texte_lesen(arg.texte / "beschreibung.en.md")
        kurz_de, lang_de = texte_lesen(arg.texte / "beschreibung.de.md")
        block = feld_ersetzen(block, "description", sprachen({"en": kurz_en, "de": kurz_de}, als_template=False))
        block = feld_ersetzen(block, "fullDescription", sprachen({"en": lang_en, "de": lang_de}, als_template=True))
    apps = apps[:anfang] + block + apps[ende:]

    # ── _lib.ts ───────────────────────────────────────────────────────────
    roh = arg.chart.read_bytes()
    if roh[:2] != b"\x1f\x8b":
        raise SystemExit("Chart ist kein gzip")
    b64 = base64.b64encode(roh).decode()
    schluessel = list(re.finditer(r'\n\s*"insilo-[0-9.]+\.tgz": "[A-Za-z0-9+/=]+",?', lib))
    if len(schluessel) != 1:
        raise SystemExit(f"_lib.ts: {len(schluessel)} Insilo-Schlüssel statt einem")
    k = schluessel[0]
    komma = "," if k.group(0).endswith(",") else ""
    einrueck = re.match(r"\n(\s*)", k.group(0)).group(1)
    lib = lib[: k.start()] + f'\n{einrueck}"insilo-{v}.tgz": "{b64}"{komma}' + lib[k.end():]

    m = re.search(r"const CANONICAL_EPOCH_MS = (\d+);", lib)
    if not m:
        raise SystemExit("_lib.ts: CANONICAL_EPOCH_MS nicht gefunden")
    epoch_alt = int(m.group(1))
    epoch_neu = (epoch_alt // 1_000_000_000 + 1) * 1_000_000_000
    lib = lib[: m.start(1)] + str(epoch_neu) + lib[m.end(1):]

    apps_datei.write_text(apps, encoding="utf-8")
    lib_datei.write_text(lib, encoding="utf-8")

    sha = hashlib.sha256(roh).hexdigest()
    if arg.pr_text:
        arg.pr_text.write_text(
            "\n".join(
                [
                    f"Insilo {alt} → {v}, gebaut von der Action `markt.yml` im Insilo-Repo nach dem Release.",
                    "",
                    f"- `functions/_apps.ts`: Version {alt} → {v}, Notiz{'en' if len(neue) > 1 else ''} "
                    + ", ".join(d.stem for d in neue)
                    + " vorn in `upgradeDescription`.",
                    (
                        f"- `functions/_lib.ts`: `insilo-{v}.tgz` (Release-Anhang, sha256 `{sha}`), "
                        f"`CANONICAL_EPOCH_MS` {epoch_alt} → {epoch_neu}."
                    ),
                    "",
                    "Vor dem PR lokal mit wrangler bewiesen: Hash, Chart byte-gleich, Detail mit Version und chartName.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    print(f"insilo {v}: {titel}")


if __name__ == "__main__":
    main()
