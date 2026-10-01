// Vor dem Rundgang: Die Besprechungen aus e2e/beispiel/daten.sql sind da,
// und sie tragen Schlagworte — die legt dies hier über die API an, wie ein
// Mensch es täte (und wie es das Protokoll dann auch zeigt).

const BASIS = process.env.INSILO_URL ?? "http://localhost:3020";
const NUTZER = process.env.INSILO_USER ?? "devuser";

async function anfrage<T>(methode: string, pfad: string, koerper?: unknown): Promise<T> {
  const r = await fetch(BASIS + pfad, {
    method: methode,
    headers: { "Content-Type": "application/json", "Remote-User": NUTZER },
    body: koerper === undefined ? undefined : JSON.stringify(koerper),
  });
  if (!r.ok) throw new Error(`${methode} ${pfad}: ${r.status} ${await r.text()}`);
  return (r.status === 204 ? null : await r.json()) as T;
}

type MitId = { id: string };
const M = (n: number) => `11111111-1111-4111-8111-00000000000${n}`;

export default async function vorbereitung() {
  const besprechungen = await anfrage<MitId[]>("GET", "/api/v1/meetings");
  if (besprechungen.length === 0) {
    throw new Error("Keine Beispieldaten — vorher e2e/beispiel/daten.sql einspielen.");
  }
  if ((await anfrage<MitId[]>("GET", "/api/v1/tags")).length > 0) return;

  const tag = async (name: string) => (await anfrage<MitId>("POST", "/api/v1/tags", { name, color: "#587898" })).id;
  const [mandat, steuer, intern, akquise] = [await tag("Mandat"), await tag("Umwandlungssteuer"), await tag("Intern"), await tag("Akquise")];
  for (const [m, t] of [[1, mandat], [1, steuer], [2, intern], [3, akquise]] as const) {
    await anfrage("POST", `/api/v1/meetings/${M(m)}/tags`, { tag_id: t });
  }
  await anfrage("PATCH", `/api/v1/meetings/${M(2)}`, { title: "Teamrunde Steuerabteilung KW 40" });
}
