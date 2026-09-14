/**
 * The upload path must bypass the middleware (which caps the body at
 * 10 MB) and still carry the same headers as every other call. Background:
 * app/api/v1/recordings/route.ts.
 */
import { createServer, type IncomingHttpHeaders, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { unstable_doesMiddlewareMatch } from "next/experimental/testing/server";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { config } from "@/middleware";

describe("middleware matcher", () => {
  const passt = (url: string) =>
    unstable_doesMiddlewareMatch({ config, url: `http://box${url}` });

  it("skips exactly the upload path", () => {
    expect(passt("/api/v1/recordings")).toBe(false);
  });

  it("still covers every other backend call", () => {
    expect(passt("/api/v1/meetings")).toBe(true);
    expect(passt("/api/v1/meetings/abc/summary")).toBe(true);
    expect(passt("/api/v1/recordingsX")).toBe(true);
    // A sub-path would otherwise reach the backend through the rewrite
    // without the shared secret.
    expect(passt("/api/v1/recordings/abc")).toBe(true);
  });

  it("leaves pages alone", () => {
    expect(passt("/aufnahme")).toBe(false);
  });
});

describe("POST /api/v1/recordings", () => {
  let server: Server;
  let angekommen = 0;
  let kopfzeilen: IncomingHttpHeaders = {};

  beforeAll(async () => {
    server = createServer((req, res) => {
      angekommen = 0;
      kopfzeilen = req.headers;
      req.on("data", (stueck: Buffer) => (angekommen += stueck.length));
      req.on("end", () => {
        res.writeHead(201, { "content-type": "application/json" });
        res.end(JSON.stringify({ id: "m1" }));
      });
    });
    await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
    const { port } = server.address() as AddressInfo;
    process.env.INSILO_BACKEND_INTERNAL = `http://127.0.0.1:${port}`;
    process.env.INSILO_INTERNAL_TOKEN = "geheim";
  });

  afterAll(() => {
    server.close();
    delete process.env.INSILO_BACKEND_INTERNAL;
    delete process.env.INSILO_INTERNAL_TOKEN;
  });

  it("streams a body far above 10 MB through, with the secret set", async () => {
    const { POST } = await import("@/app/api/v1/recordings/route");
    const MB = 1024 * 1024;
    const groesse = 32 * MB;
    let gesendet = 0;
    const rumpf = new ReadableStream<Uint8Array>({
      pull(ctrl) {
        if (gesendet >= groesse) return ctrl.close();
        ctrl.enqueue(new Uint8Array(MB));
        gesendet += MB;
      },
    });
    const anfrage = new Request("http://box/api/v1/recordings", {
      method: "POST",
      body: rumpf,
      // @ts-expect-error — Node needs this for a streamed body.
      duplex: "half",
      headers: {
        "content-type": "multipart/form-data; boundary=x",
        // A browser cannot be trusted with either of these.
        "x-insilo-internal": "vom-browser",
        "x-bfl-user": "jemand",
        "remote-user": "anna",
        // undici rejects any request carrying it.
        expect: "100-continue",
      },
    });

    const antwort = await POST(anfrage);

    expect(antwort.status).toBe(201);
    expect(await antwort.json()).toEqual({ id: "m1" });
    expect(angekommen).toBe(groesse);
    expect(kopfzeilen["x-insilo-internal"]).toBe("geheim");
    expect(kopfzeilen["x-bfl-user"]).toBe("anna");
    expect(kopfzeilen.expect).toBeUndefined();
    expect(kopfzeilen["content-type"]).toBe("multipart/form-data; boundary=x");
  });

  it("answers 502 when the backend is down", async () => {
    const { POST } = await import("@/app/api/v1/recordings/route");
    const vorher = process.env.INSILO_BACKEND_INTERNAL;
    // A port that was just free: nothing listens there any more.
    const frei = createServer();
    await new Promise<void>((r) => frei.listen(0, "127.0.0.1", r));
    const { port } = frei.address() as AddressInfo;
    await new Promise((r) => frei.close(r));
    process.env.INSILO_BACKEND_INTERNAL = `http://127.0.0.1:${port}`;
    try {
      const antwort = await POST(
        new Request("http://box/api/v1/recordings", { method: "POST", body: "x" }),
      );
      expect(antwort.status).toBe(502);
    } finally {
      process.env.INSILO_BACKEND_INTERNAL = vorher;
    }
  });
});
