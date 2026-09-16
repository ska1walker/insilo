"""Welche Besprechungen ein angeschlossenes CRM übernimmt.

**Der Anlass.** Beacon las den gemeinsamen Ordner der Box und übernahm
alles, was Insilo dort ablegte: Kundengespräche, aber ebenso interne
Runden und Sprachnotizen. Filtern konnte Beacon nur am Namen der Vorlage,
und der ist pro Organisation umbenennbar (aus „Vertriebsgespräch" wird
„Kundentermin") oder bei eigenen Vorlagen frei gewählt.

**Die Entscheidung.** Ob ein Gespräch ins CRM gehört, legt Insilo fest,
an der Vorlage — aber getrennt von ihr (Migration 0021): *wie* eine
Besprechung zusammengefasst wird und *wohin* sie geht, sind zwei Fragen.
Die Markierung steht dann in der Datei im gemeinsamen Ordner und im
Webhook, und das CRM richtet sich nur noch nach ihr.

Wirksam ist `coalesce(template_weitergabe.an_crm, templates.an_crm)`:
die Organisation kann von der Voreinstellung abweichen. Eine Besprechung
ohne Vorlage geht nicht ins CRM — ohne Vorlage weiß niemand, was für ein
Gespräch es war.

**Was es nicht regelt.** Der gemeinsame Ordner bekommt weiterhin jede
Zusammenfassung; Relay liest ihn mit, und was Relay sehen soll, ist eine
eigene, noch offene Entscheidung. Die Markierung sagt einem CRM, was es
übernehmen soll — sie hält nichts vom Ordner fern.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg

# Für Abfragen, die `m` (meetings) schon führen: liefert die wirksame
# Markierung als Spalte `an_crm`. Ohne Vorlage: nein.
SPALTE = """
    coalesce(
      (select w.an_crm from public.template_weitergabe w
        where w.org_id = m.org_id and w.template_id = m.template_id),
      (select t.an_crm from public.templates t where t.id = m.template_id),
      false
    ) as an_crm
"""


async def fuer_besprechung(conn: asyncpg.Connection, meeting_id: UUID) -> bool:
    """Geht diese Besprechung ins CRM?"""
    wert = await conn.fetchval(
        f"select {SPALTE} from public.meetings m where m.id = $1",
        meeting_id,
    )
    return bool(wert)


async def fuer_vorlage(
    conn: asyncpg.Connection, org_id: UUID, template_id: UUID,
) -> tuple[bool, bool, bool]:
    """(wirksam, Voreinstellung, weicht ab) für eine Vorlage in einer Organisation."""
    zeile = await conn.fetchrow(
        """
        select t.an_crm as voreinstellung, w.an_crm as abweichung
        from public.templates t
        left join public.template_weitergabe w
          on w.template_id = t.id and w.org_id = $1
        where t.id = $2
        """,
        org_id,
        template_id,
    )
    if zeile is None:
        return False, False, False
    voreinstellung = bool(zeile["voreinstellung"])
    abweichung = zeile["abweichung"]
    wirksam = voreinstellung if abweichung is None else bool(abweichung)
    return wirksam, voreinstellung, abweichung is not None
