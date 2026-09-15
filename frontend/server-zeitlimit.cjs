/**
 * Hebt Nodes Zeitlimit für eine ganze Anfrage an, bevor Next seinen Server
 * startet. Geladen im Dockerfile: `node --require ./server-zeitlimit.cjs server.js`.
 *
 * **Warum.** Node beendet jede Anfrage, die nach 300 s nicht vollständig
 * angekommen ist (`server.requestTimeout`, Vorgabe seit Node 18), und Next
 * setzt keinen eigenen Wert. Ein Upload, der länger dauert, bricht mit
 * ECONNRESET ab — eine 90-Minuten-Aufnahme (rund 90 MB) über ein Mobilnetz
 * mit 2 Mbit/s braucht etwa sechs Minuten und scheiterte damit bei jedem
 * Versuch, seit 0.1.96 der Upload überhaupt vollständig durchgeht. Gefunden
 * in der Prüfung vor 0.1.98.
 *
 * Zwei Stunden reichen für 500 MB bei 1 Mbit/s. `headersTimeout` (60 s für
 * die Kopfzeilen) bleibt, wie es ist: Wer nicht einmal die schickt, soll
 * nicht zwei Stunden eine Verbindung halten.
 */
"use strict";

const http = require("node:http");

const STANDARD_MS = 2 * 60 * 60 * 1000;
const roh = Number.parseInt(process.env.INSILO_REQUEST_TIMEOUT_MS ?? "", 10);
const zeitlimit = Number.isFinite(roh) && roh >= 0 ? roh : STANDARD_MS;

const erzeugen = http.createServer;
http.createServer = function createServerMitZeitlimit(...argumente) {
  const server = erzeugen.apply(this, argumente);
  server.requestTimeout = zeitlimit;
  return server;
};

module.exports = { zeitlimit };
