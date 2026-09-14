// Next's server runtime puts AsyncLocalStorage on globalThis at startup
// (next/dist/server/node-environment-baseline.js). Route handlers that log
// through Next's patched console expect it; plain Vitest does not set it.
import { AsyncLocalStorage } from "node:async_hooks";

(globalThis as { AsyncLocalStorage?: unknown }).AsyncLocalStorage ??= AsyncLocalStorage;
