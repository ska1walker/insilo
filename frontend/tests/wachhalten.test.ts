import { describe, expect, it } from "vitest";
import { Wachhalter } from "@/lib/wachhalten";

function umgebung(sichtbar = true) {
  const hoerer = new Set<() => void>();
  const doc = {
    visibilityState: sichtbar ? "visible" : "hidden",
    addEventListener: (_: string, f: () => void) => hoerer.add(f),
    removeEventListener: (_: string, f: () => void) => hoerer.delete(f),
  };
  const sperren: { freigegeben: boolean; release(): Promise<void> }[] = [];
  let offen: ((s: (typeof sperren)[number]) => void)[] = [];
  const nav = {
    wakeLock: {
      request: () =>
        new Promise<(typeof sperren)[number]>((r) => {
          offen.push(r);
        }),
    },
  };
  const gewaehren = () => {
    const warten = offen;
    offen = [];
    for (const r of warten) {
      const s = {
        freigegeben: false,
        release() {
          this.freigegeben = true;
          return Promise.resolve();
        },
      };
      sperren.push(s);
      r(s);
    }
  };
  const sichtbarkeit = (wert: "visible" | "hidden") => {
    doc.visibilityState = wert;
    hoerer.forEach((f) => f());
  };
  return { doc, nav, sperren, gewaehren, sichtbarkeit, hoerer, anfragen: () => offen.length };
}

const ruhe = () => new Promise((r) => setTimeout(r, 0));

describe("Wachhalter", () => {
  it("holds a lock while on and releases it when off", async () => {
    const u = umgebung();
    const h = new Wachhalter(u.nav, u.doc);
    h.an();
    u.gewaehren();
    await ruhe();
    expect(u.sperren).toHaveLength(1);
    h.aus();
    expect(u.sperren[0].freigegeben).toBe(true);
    expect(u.hoerer.size).toBe(0);
  });

  it("asks again when the tab becomes visible after the browser dropped the lock", async () => {
    const u = umgebung(false);
    const h = new Wachhalter(u.nav, u.doc);
    h.an();
    expect(u.anfragen()).toBe(0); // hidden tabs are refused, so it doesn't try
    u.sichtbarkeit("visible");
    expect(u.anfragen()).toBe(1);
    u.gewaehren();
    await ruhe();
    h.aus();
  });

  it("releases a lock that arrives after recording ended", async () => {
    const u = umgebung();
    const h = new Wachhalter(u.nav, u.doc);
    h.an();
    h.aus();
    u.gewaehren();
    await ruhe();
    expect(u.sperren[0].freigegeben).toBe(true);
  });

  it("reports when the browser has no wake lock", async () => {
    const u = umgebung();
    const meldungen: boolean[] = [];
    const h = new Wachhalter({}, u.doc, (v) => meldungen.push(v));
    expect(h.verfuegbar).toBe(false);
    h.an();
    await ruhe();
    expect(meldungen).toEqual([]);
    expect(h.verfuegbar).toBe(false);
  });

  it("reports a refused request", async () => {
    const u = umgebung();
    const meldungen: boolean[] = [];
    const nav = { wakeLock: { request: () => Promise.reject(new Error("NotAllowedError")) } };
    const h = new Wachhalter(nav as never, u.doc, (v) => meldungen.push(v));
    h.an();
    await ruhe();
    expect(meldungen).toEqual([false]);
  });
});
