"""Ein zu langes Transkript vorverdichten, bevor es zusammengefasst wird.

**Das Problem.** `tasks/summarize.py` legt das ganze Transkript in die
Anfrage ans Sprachmodell. Das ging gut, solange keine Besprechung fertig
wurde, die länger als zwanzig Minuten war — seit 0.1.99 laufen auch
anderthalb Stunden durch. Anderthalb Stunden sind grob zwölf- bis
fünfzehntausend Wörter, also über zwanzigtausend Token. Ein Modell mit
acht- oder sechzehntausend Token Kontext nimmt das nicht an, und was
schlimmer ist: manche Endpunkte nehmen es klaglos an und schneiden
stillschweigend vorn ab. Dann fehlt in der Zusammenfassung die erste
Stunde, ohne dass irgendwo etwas davon steht.

**Der Weg.** Ist das Transkript zu lang, wird es abschnittsweise zu
dichter Prosa zusammengezogen, und diese Prosa geht als „Transkript" in
die eigentliche Zusammenfassung. Das ist das übliche Falten: viele kleine
Anfragen, dann eine große. Die eigentliche Zusammenfassung bleibt dabei
unverändert — sie arbeitet weiter mit ihrer Vorlage und ihrem Schema und
merkt nicht, dass sie kürzeren Text bekommt.

**Was dabei verloren geht.** Genauigkeit im Wortlaut. Die verdichtete
Fassung ist eine Nacherzählung, kein Protokoll; wörtliche Zitate daraus
sind nicht mehr wörtlich. Deshalb wird nur verdichtet, was sonst gar
nicht durchginge, und die Aufforderung besteht ausdrücklich auf Namen,
Zahlen, Terminen und Beschlüssen — das ist es, was eine Kanzlei aus einer
Besprechung braucht. Der volle Wortlaut bleibt unangetastet in
`transcripts` und in der Ablage-Datei.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# Mehr als zwei Runden Falten bringen nichts: was danach noch zu lang ist,
# war nie ein Transkript, sondern ein Fehler.
MAX_RUNDEN = 3

AUFFORDERUNG = {
    "de": (
        "Das ist ein Abschnitt aus dem Protokoll einer Besprechung. Fasse "
        "ihn dicht zusammen, in ganzen Sätzen. Übernimm dabei ausnahmslos: "
        "alle genannten Namen, Zahlen, Beträge, Termine und Fristen, jeden "
        "Beschluss und jede Aufgabe samt der Person, die sie übernimmt. "
        "Lass Begrüßungen, Wiederholungen und Nebengespräche weg. Schreibe "
        "nur die Zusammenfassung, ohne Vorrede."
    ),
    "en": (
        "This is one part of a meeting transcript. Summarize it densely, in "
        "full sentences. Keep, without exception: every name, number, "
        "amount, date and deadline mentioned, every decision, and every "
        "action item together with the person taking it on. Leave out "
        "greetings, repetitions and side conversations. Write only the "
        "summary, with no preamble."
    ),
    "fr": (
        "Voici une partie du compte rendu d'une réunion. Résumez-la de "
        "manière dense, en phrases complètes. Conservez sans exception : "
        "tous les noms, chiffres, montants, dates et échéances cités, "
        "chaque décision et chaque tâche avec la personne qui s'en charge. "
        "Omettez les salutations, les répétitions et les conversations "
        "annexes. N'écrivez que le résumé, sans préambule."
    ),
    "es": (
        "Esta es una parte del acta de una reunión. Resúmala de forma densa, "
        "en oraciones completas. Conserve sin excepción: todos los nombres, "
        "cifras, importes, fechas y plazos mencionados, cada decisión y cada "
        "tarea junto con la persona que la asume. Omita saludos, "
        "repeticiones y conversaciones paralelas. Escriba solo el resumen, "
        "sin preámbulo."
    ),
    "it": (
        "Questa è una parte del verbale di una riunione. La riassuma in modo "
        "denso, in frasi complete. Conservi senza eccezioni: tutti i nomi, i "
        "numeri, gli importi, le date e le scadenze citati, ogni decisione e "
        "ogni compito insieme alla persona che se ne fa carico. Ometta "
        "saluti, ripetizioni e conversazioni secondarie. Scriva solo il "
        "riassunto, senza preamboli."
    ),
}

UEBERSCHRIFT = {
    "de": "Abschnitt {nr} von {gesamt}",
    "en": "Part {nr} of {gesamt}",
    "fr": "Partie {nr} sur {gesamt}",
    "es": "Parte {nr} de {gesamt}",
    "it": "Parte {nr} di {gesamt}",
}


def aufforderung(locale: str) -> str:
    return AUFFORDERUNG.get(locale, AUFFORDERUNG["de"])


def zu_lang(text: str, grenze: int) -> bool:
    return grenze > 0 and len(text) > grenze


def teilen(text: str, grenze: int) -> list[str]:
    """In Abschnitte unterhalb der Grenze, an Zeilenenden.

    Das Transkript kommt als `[Name]: Text` je Zeile. An Zeilenenden zu
    trennen hält jede Äußerung beisammen und lässt die Sprecherzuordnung
    heil — mitten in einer Zeile zu schneiden ergäbe einen Abschnitt, der
    mit einem Satzende ohne Namen beginnt.

    Eine einzelne Zeile, die für sich schon zu lang ist (ein Transkript
    ohne Sprecher ist *eine* Zeile), wird hart geteilt.
    """
    if grenze <= 0 or not text:
        return [text] if text else []

    abschnitte: list[str] = []
    laufend: list[str] = []
    laenge = 0

    def abschliessen() -> None:
        nonlocal laufend, laenge
        if laufend:
            abschnitte.append("\n".join(laufend))
            laufend = []
            laenge = 0

    for zeile in text.split("\n"):
        while len(zeile) > grenze:
            abschliessen()
            abschnitte.append(zeile[:grenze])
            zeile = zeile[grenze:]
        if laenge + len(zeile) + 1 > grenze:
            abschliessen()
        laufend.append(zeile)
        laenge += len(zeile) + 1
    abschliessen()
    return abschnitte


def zusammensetzen(teile: list[str], locale: str) -> str:
    """Die verdichteten Abschnitte in der richtigen Reihenfolge, benannt.

    Die Überschriften helfen dem Modell in der zweiten Runde, den Ablauf
    zu erkennen — ohne sie liest sich das Ganze wie eine Sammlung
    zusammenhangloser Absätze.
    """
    muster = UEBERSCHRIFT.get(locale, UEBERSCHRIFT["de"])
    gesamt = len(teile)
    return "\n\n".join(
        f"{muster.format(nr=i + 1, gesamt=gesamt)}\n{t.strip()}"
        for i, t in enumerate(teile)
        if t.strip()
    )
