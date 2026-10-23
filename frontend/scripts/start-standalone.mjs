import { cpSync, existsSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const frontendRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const buildRoot = path.join(frontendRoot, ".next");
const standaloneRoot = path.join(buildRoot, "standalone");
const staticSource = path.join(buildRoot, "static");
const staticTarget = path.join(standaloneRoot, ".next", "static");
const server = path.join(standaloneRoot, "server.js");

if (!existsSync(server) || !existsSync(staticSource)) {
  throw new Error("Standalone build is missing; run npm run build first.");
}

mkdirSync(path.dirname(staticTarget), { recursive: true });
cpSync(staticSource, staticTarget, { recursive: true });

const child = spawn(process.execPath, [server], {
  cwd: standaloneRoot,
  env: process.env,
  stdio: "inherit",
});

const forwardSignal = (signal) => child.kill(signal);
process.on("SIGINT", () => forwardSignal("SIGINT"));
process.on("SIGTERM", () => forwardSignal("SIGTERM"));
child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  else process.exit(code ?? 1);
});
