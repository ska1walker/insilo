/**
 * The upload path must bypass the middleware (which caps the body at
 * 10 MB), stream with backpressure, and still carry the same headers as
 * every other call. Background: app/api/v1/recordings/route.ts.
 */
import { createServer, type IncomingHttpHeaders, type Server, type ServerResponse } from "node:http";
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

type Senke = (req: import("node:http").IncomingMessage, res: ServerResponse) => void;

async function lauschen(server: Server): Promise<number> {
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  return (server.address() as AddressInfo).port;
}

async function senden(init: RequestInit & { duplex?: "half" }): Promise<Response> {
  const { POST } = await import("@/app/api/v1/recordings/route");
  return POST(new Request("http://box/api/v1/recordings", { method: "POST", ...init }));
}

function rumpf(groesse: number): ReadableStream<Uint8Array> {
  const MB = 1024 * 1024;
  let gesendet = 0;
  return new ReadableStream<Uint8Array>({
    pull(ctrl) {
      if (gesendet >= groesse) return ctrl.close();
      ctrl.enqueue(new Uint8Array(MB));
      gesendet += MB;
    },
  });
}

describe("POST /api/v1/recordings", () => {
  let backend: Server;
  let senke: Senke = () => {};

  beforeAll(async () => {
    backend = createServer((req, res) => senke(req, res));
    const port = await lauschen(backend);
    process.env.INSILO_BACKEND_INTERNAL = `http://127.0.0.1:${port}`;
    process.env.INSILO_INTERNAL_TOKEN = "geheim";
  });

  afterAll(() => {
    backend.close();
    delete process.env.INSILO_BACKEND_INTERNAL;
    delete process.env.INSILO_INTERNAL_TOKEN;
  });

  it("streams a body far above 10 MB through, with the secret set", async () => {
    let angekommen = 0;
    let kopfzeilen: IncomingHttpHeaders = {};
    senke = (req, res) => {
      kopfzeilen = req.headers;
      req.on("data", (stueck: Buffer) => (angekommen += stueck.length));
      req.on("end", () => {
        res.writeHead(201, { "content-type": "application/json" });
        res.end(JSON.stringify({ id: "m1" }));
      });
    };
    const groesse = 32 * 1024 * 1024;
    const antwort = await senden({
      body: rumpf(groesse),
      duplex: "half",
      headers: {
        "content-type": "multipart/form-data; boundary=x",
        // A browser cannot be trusted with either of these.
        "x-insilo-internal": "vom-browser",
        "x-bfl-user": "jemand",
        "remote-user": "anna",
      },
    });

    expect(antwort.status).toBe(201);
    expect(await antwort.json()).toEqual({ id: "m1" });
    expect(angekommen).toBe(groesse);
    expect(kopfzeilen["x-insilo-internal"]).toBe("geheim");
    expect(kopfzeilen["x-bfl-user"]).toBe("anna");
    expect(kopfzeilen["content-type"]).toBe("multipart/form-data; boundary=x");
  });

  it("strips hop-by-hop headers, including expect", async () => {
    const { kopfzeilenFuersBackend } = await import("@/lib/weiterleitung");
    const k = kopfzeilenFuersBackend(
      new Headers({
        expect: "100-continue",
        "transfer-encoding": "chunked",
        host: "box",
        connection: "keep-alive",
        "content-length": "12",
      }),
    );
    expect(k.expect).toBeUndefined();
    expect(k["transfer-encoding"]).toBeUndefined();
    expect(k.host).toBeUndefined();
    expect(k.connection).toBeUndefined();
    expect(k["content-length"]).toBe("12");
    expect(k["x-insilo-internal"]).toBe("geheim");
  });

  it("passes a refusal from the backend through, after the whole body", async () => {
    let angekommen = 0;
    senke = (req, res) => {
      // Like Starlette: read the whole form, then refuse.
      req.on("data", (stueck: Buffer) => (angekommen += stueck.length));
      req.on("end", () => {
        res.writeHead(413, { "content-type": "application/json" });
        res.end(JSON.stringify({ detail: "zu groß" }));
      });
    };
    const antwort = await senden({
      body: rumpf(16 * 1024 * 1024),
      duplex: "half",
    });
    expect(antwort.status).toBe(413);
    expect(await antwort.json()).toEqual({ detail: "zu groß" });
    expect(angekommen).toBe(16 * 1024 * 1024);
  });

  it("answers 502 when the backend takes the body and never answers", async () => {
    senke = (req) => {
      req.resume(); // read everything, answer nothing
    };
    process.env.INSILO_BACKEND_TIMEOUT_MS = "300";
    try {
      const antwort = await senden({ body: rumpf(2 * 1024 * 1024), duplex: "half" });
      expect(antwort.status).toBe(502);
    } finally {
      delete process.env.INSILO_BACKEND_TIMEOUT_MS;
    }
  });

  it("answers 502 when the backend is down", async () => {
    const vorher = process.env.INSILO_BACKEND_INTERNAL;
    const frei = createServer();
    const port = await lauschen(frei);
    await new Promise((r) => frei.close(r));
    process.env.INSILO_BACKEND_INTERNAL = `http://127.0.0.1:${port}`;
    try {
      const antwort = await senden({
        body: "x",
      });
      expect(antwort.status).toBe(502);
    } finally {
      process.env.INSILO_BACKEND_INTERNAL = vorher;
    }
  });
});
