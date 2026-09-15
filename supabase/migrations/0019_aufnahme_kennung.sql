-- ============================================================================
-- 0019 — Eine Aufnahme wird nur einmal zur Besprechung
--
-- Seit 0.1.96 sichert der Browser jede Aufnahme, bis die Box sie angenommen
-- hat, und bietet sie sonst erneut an. Kam der erste Upload an, die Antwort
-- aber nicht (Funkloch in dem Moment, Tab geschlossen), legte „Erneut
-- senden" dieselbe Besprechung ein zweites Mal an.
--
-- Der Browser schickt deshalb seit 0.1.98 die Kennung der Aufnahme mit
-- (`client_id`, eine UUID aus `lib/aufnahmen.ts`), die Box legt sie in
-- `metadata.client_id` ab und gibt bei einer Wiederholung die schon
-- angelegte Besprechung zurück. Die Prüfung davor steht im Endpunkt; dieser
-- Index fängt den Fall, dass zwei Wiederholungen gleichzeitig ankommen.
--
-- Nur Zeilen mit Kennung: ältere Besprechungen und Aufrufe ohne Kennung
-- (die externe Schnittstelle, Skripte) bleiben unberührt. Der Init-Container
-- führt jede Datei bei jedem Start aus — daher `if not exists`.
-- ============================================================================

create unique index if not exists meetings_org_client_id_key
  on public.meetings (org_id, (metadata->>'client_id'))
  where metadata ? 'client_id';
