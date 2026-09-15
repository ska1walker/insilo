import { describe, expect, it } from "vitest";
import { ApiError, anfrageKopfzeilen, localeAusCookie } from "@/lib/api/client";
import { hochladen, type Fortschritt } from "@/lib/api/hochladen";
import { fortschrittWerte } from "@/lib/format";

describe("anfrageKopfzeilen", () => {
  it("sets the identity and takes the language from the cookie", () => {
    const k = anfrageKopfzeilen("foo=1; insilo-locale=fr; bar=2");
    expect(k["X-Bfl-User"]).toBeTruthy();
    expect(k["Accept-Language"]).toBe("fr");
  });

  it("ignores unknown languages and keeps an explicit one", () => {
    expect(localeAusCookie("insilo-locale=xx")).toBeNull();
    expect(anfrageKopfzeilen("insilo-locale=fr", { "Accept-Language": "it" })["Accept-Language"]).toBe("it");
    expect(anfrageKopfzeilen(null)["Accept-Language"]).toBeUndefined();
  });
});

/** Just enough XMLHttpRequest to drive `hochladen` without a browser. */
class FakeXhr {
  status = 0;
  statusText = "";
  responseText = "";
  gesendet: unknown = null;
  kopfzeilen: Record<string, string> = {};
  methode = "";
  adresse = "";
  antwortTyp = "application/json";
  upload: { onprogress: ((e: ProgressEvent) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  onabort: (() => void) | null = null;
  open(m: string, a: string) {
    this.methode = m;
    this.adresse = a;
  }
  setRequestHeader(n: string, w: string) {
    this.kopfzeilen[n] = w;
  }
  send(rumpf: unknown) {
    this.gesendet = rumpf;
  }
  getResponseHeader() {
    return this.antwortTyp;
  }
  fortschritt(geladen: number, gesamt: number) {
    this.upload.onprogress?.({ lengthComputable: true, loaded: geladen, total: gesamt } as ProgressEvent);
  }
  antworten(status: number, text: string) {
    this.status = status;
    this.statusText = status === 201 ? "Created" : "Error";
    this.responseText = text;
    this.onload?.();
  }
}

function aufbauen(beiFortschritt?: (f: Fortschritt) => void) {
  const xhr = new FakeXhr();
  const form = new FormData();
  form.append("title", "Probe");
  const zusage = hochladen<{ id: string }>("/api/v1/recordings", form, {
    beiFortschritt,
    xhrFabrik: () => xhr as never,
    cookie: "insilo-locale=en",
  });
  return { xhr, form, zusage };
}

describe("hochladen", () => {
  it("posts the form with the same headers as apiRequest and resolves JSON", async () => {
    const { xhr, form, zusage } = aufbauen();
    expect(xhr.methode).toBe("POST");
    expect(xhr.adresse).toBe("/api/v1/recordings");
    expect(xhr.gesendet).toBe(form);
    expect(xhr.kopfzeilen["X-Bfl-User"]).toBeTruthy();
    expect(xhr.kopfzeilen["Accept-Language"]).toBe("en");
    xhr.antworten(201, JSON.stringify({ id: "m1" }));
    await expect(zusage).resolves.toEqual({ id: "m1" });
  });

  it("rejects a refusal as ApiError carrying the parsed body", async () => {
    const { xhr, zusage } = aufbauen();
    xhr.antworten(413, JSON.stringify({ detail: "Die Datei ist zu groß." }));
    const fehler = await zusage.catch((e) => e);
    expect(fehler).toBeInstanceOf(ApiError);
    expect(fehler.status).toBe(413);
    expect(fehler.body).toEqual({ detail: "Die Datei ist zu groß." });
  });

  it("rejects a network failure as something other than ApiError", async () => {
    for (const art of ["onerror", "ontimeout", "onabort"] as const) {
      const { xhr, zusage } = aufbauen();
      xhr[art]?.();
      const fehler = await zusage.catch((e) => e);
      expect(fehler).toBeInstanceOf(Error);
      expect(fehler).not.toBeInstanceOf(ApiError);
    }
  });

  it("reports progress at most once per whole percent", async () => {
    const meldungen: Fortschritt[] = [];
    const { xhr, zusage } = aufbauen((f) => meldungen.push(f));
    const gesamt = 90_000_000;
    for (let geladen = 0; geladen <= gesamt; geladen += 90_000) xhr.fortschritt(geladen, gesamt);
    expect(meldungen.length).toBe(101); // 0 … 100 %
    expect(meldungen.at(-1)).toEqual({ geladen: gesamt, gesamt });
    xhr.antworten(201, "{}");
    await zusage;
  });
});

describe("fortschrittWerte", () => {
  it("formats percent and amounts in the locale", () => {
    const w = fortschrittWerte(38_100_000, 94_800_000, "de");
    expect(w.prozent).toBe(40);
    expect(w.gesamt).toBe("90 MB");
    expect(w.fertig).toBe(false);
  });

  it("is finished only when everything has left the browser", () => {
    expect(fortschrittWerte(100, 100).fertig).toBe(true);
    expect(fortschrittWerte(0, 0).fertig).toBe(false);
    expect(fortschrittWerte(150, 100).prozent).toBe(100);
  });
});
