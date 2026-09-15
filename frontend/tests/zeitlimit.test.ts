/**
 * Node ends a request after 300 s (`server.requestTimeout`), and Next sets
 * no value of its own. Measured before 0.1.98: a 10 MB upload at 30 kB/s
 * through the standalone server got HTTP 408 after 329 s. See
 * server-zeitlimit.cjs.
 */
import { readFileSync } from "node:fs";
import http from "node:http";
import { createRequire } from "node:module";
import { describe, expect, it } from "vitest";

const require = createRequire(import.meta.url);

describe("server-zeitlimit.cjs", () => {
  it("raises the request timeout of every server created afterwards", () => {
    const vorher = http.createServer;
    try {
      const { zeitlimit } = require("../server-zeitlimit.cjs") as { zeitlimit: number };
      expect(zeitlimit).toBe(2 * 60 * 60 * 1000);
      const server = http.createServer();
      expect(server.requestTimeout).toBe(zeitlimit);
    } finally {
      http.createServer = vorher;
    }
  });

  it("is loaded by the container before Next starts", () => {
    const dockerfile = readFileSync(new URL("../Dockerfile", import.meta.url), "utf8");
    expect(dockerfile).toMatch(/COPY .*server-zeitlimit\.cjs/);
    expect(dockerfile).toMatch(/CMD \["node", "--require", "\.\/server-zeitlimit\.cjs", "server\.js"\]/);
  });
});
