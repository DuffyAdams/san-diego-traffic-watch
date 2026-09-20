import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const projectDir = path.resolve(frontendDir, "..");
const backendOnly = process.argv.includes("--backend-only");
const pythonCommand = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
const children = [];

function start(command, args, options) {
  const child = spawn(command, args, { stdio: "inherit", ...options });
  children.push(child);
  child.on("exit", (code, signal) => {
    if (signal || code === 0) return;
    process.exitCode = code ?? 1;
    stopChildren();
  });
  return child;
}

function stopChildren() {
  for (const child of children) {
    if (!child.killed) child.kill();
  }
}

start(pythonCommand, ["-m", "backend"], {
  cwd: projectDir,
  env: { ...process.env, TESTMODE: "true" },
});

if (!backendOnly) {
  const viteCli = path.join(frontendDir, "node_modules", "vite", "bin", "vite.js");
  start(process.execPath, [viteCli, "--mode", "backend"], { cwd: frontendDir, env: process.env });
}

process.on("SIGINT", () => {
  stopChildren();
  process.exit(0);
});
process.on("SIGTERM", () => {
  stopChildren();
  process.exit(0);
});
