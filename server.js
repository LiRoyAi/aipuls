/**
 * Express.js wrapper around portal.py
 *
 * Use this for traditional server deployments:
 *   Railway, Render, Fly.io, DigitalOcean, VPS, Docker
 *
 * NOT needed for Vercel — Vercel uses api/index.py directly via its
 * Python runtime (no subprocess, lower cold-start latency).
 *
 * How it works:
 *   1. Spawns portal.py on an internal port (PORTAL_PORT)
 *   2. Waits until portal.py is accepting connections (polls /robots.txt)
 *   3. Express proxies every incoming request to portal.py
 *   4. Gracefully shuts down portal.py on SIGTERM/SIGINT
 *
 * Usage:
 *   npm install
 *   node server.js
 *
 * Or via npm:
 *   npm start
 */

"use strict";

const express      = require("express");
const { createProxyMiddleware } = require("http-proxy-middleware");
const { spawn }    = require("child_process");
const http         = require("http");
const path         = require("path");

// ── Configuration ────────────────────────────────────────────────────────────

const PORT        = parseInt(process.env.PORT        || "3000",  10);
const PORTAL_PORT = parseInt(process.env.PORTAL_PORT || "8081",  10);
const DB_PATH     = process.env.DB_PATH  || path.join(__dirname, "neuronews.db");
const SITE_URL    = process.env.SITE_URL || "";
const PYTHON      = process.env.PYTHON   || "python3";

const PORTAL_URL  = `http://127.0.0.1:${PORTAL_PORT}`;
const READY_POLL_INTERVAL_MS = 200;
const READY_TIMEOUT_MS       = 30_000;

// ── Spawn portal.py ───────────────────────────────────────────────────────────

const portalEnv = {
  ...process.env,
  PORT:          String(PORTAL_PORT),
  DB_PATH:       DB_PATH,
  SITE_URL:      SITE_URL,
  RESEND_API_KEY: process.env.RESEND_API_KEY || "",
};

console.log(`[server] Starting portal.py on internal port ${PORTAL_PORT}…`);

const portalProc = spawn(PYTHON, [path.join(__dirname, "portal.py")], {
  env:   portalEnv,
  stdio: ["ignore", "pipe", "pipe"],
});

portalProc.stdout.on("data", (d) => process.stdout.write(`[portal] ${d}`));
portalProc.stderr.on("data", (d) => process.stderr.write(`[portal] ${d}`));

portalProc.on("exit", (code, signal) => {
  console.error(`[server] portal.py exited — code=${code} signal=${signal}`);
  process.exit(1);
});

// ── Wait until portal.py is ready ────────────────────────────────────────────

function pollReady() {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      http.get(`${PORTAL_URL}/robots.txt`, (res) => {
        if (res.statusCode < 500) {
          resolve();
        } else {
          retry();
        }
        res.resume();
      }).on("error", retry);
    };
    const retry = () => {
      if (Date.now() - start > READY_TIMEOUT_MS) {
        reject(new Error(`portal.py not ready after ${READY_TIMEOUT_MS}ms`));
      } else {
        setTimeout(check, READY_POLL_INTERVAL_MS);
      }
    };
    check();
  });
}

// ── Express + proxy ───────────────────────────────────────────────────────────

async function main() {
  try {
    await pollReady();
    console.log(`[server] portal.py ready — starting Express on :${PORT}`);
  } catch (err) {
    console.error(`[server] ${err.message}`);
    process.exit(1);
  }

  const app = express();

  // Forward all requests to portal.py
  app.use(
    "/",
    createProxyMiddleware({
      target:       PORTAL_URL,
      changeOrigin: true,
      // Forward real client IP so portal logs make sense
      on: {
        proxyReq: (proxyReq, req) => {
          proxyReq.setHeader("X-Forwarded-For", req.ip || req.socket.remoteAddress || "");
          proxyReq.setHeader("X-Forwarded-Host", req.hostname || "");
          proxyReq.setHeader("X-Forwarded-Proto", req.protocol || "http");
        },
        error: (_err, _req, res) => {
          res.status(502).end("Bad Gateway — portal.py unavailable");
        },
      },
    })
  );

  app.listen(PORT, () => {
    console.log(`[server] Express listening on http://0.0.0.0:${PORT}`);
    if (SITE_URL) console.log(`[server] Public URL: ${SITE_URL}`);
  });
}

main();

// ── Graceful shutdown ─────────────────────────────────────────────────────────

function shutdown(signal) {
  console.log(`\n[server] ${signal} received — shutting down portal.py…`);
  portalProc.kill("SIGTERM");
  setTimeout(() => process.exit(0), 2000);
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT",  () => shutdown("SIGINT"));
