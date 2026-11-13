// uso: node render.mjs <arquivo.html> <saida_dir> <fps> <t_inicio> <t_fim> <jpg|png>
// Grava quadros da página (animações CSS controladas por window.seek(t)).
// png = fundo transparente (para sobrepor no clipe de reação).
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const html = path.resolve(process.argv[2]);
const out = path.resolve(process.argv[3]);
const fps = Number(process.argv[4] || 30);
const t0 = Number(process.argv[5] || 0);
const t1 = Number(process.argv[6] || 1);
const fmt = process.argv[7] || "jpg";
const ESC = Number(process.env.ESCALA || 0.6667); // 1080x1920 desenhado, gravado em 720x1280
fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(out, { recursive: true });

const CANDIDATOS = [process.env.CHROME_PATH, "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"].filter(Boolean);
const chrome = CANDIDATOS.find(p => fs.existsSync(p));
const porta = 9400 + Math.floor(Math.random() * 500);
const perfil = fs.mkdtempSync(path.join(os.tmpdir(), "iashopee-"));
const proc = spawn(chrome, ["--headless=new", `--remote-debugging-port=${porta}`, `--user-data-dir=${perfil}`, "--hide-scrollbars",
  "--no-sandbox", "--disable-gpu", "--mute-audio", "--force-device-scale-factor=1", "--window-size=1080,1920",
  "--allow-file-access-from-files", pathToFileURL(html).href], { stdio: "ignore" });

const espera = ms => new Promise(r => setTimeout(r, ms));
let alvo;
for (let i = 0; i < 120 && !alvo; i++) {
  try { alvo = (await (await fetch(`http://127.0.0.1:${porta}/json`)).json()).find(t => t.type === "page"); } catch { }
  if (!alvo) await espera(250);
}
const ws = new WebSocket(alvo.webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener("open", r));
let id = 0; const pend = new Map();
ws.addEventListener("message", e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } });
const cdp = (method, params = {}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });

await cdp("Emulation.setDeviceMetricsOverride", { width: 1080, height: 1920, deviceScaleFactor: ESC, mobile: false });
if (fmt === "png") await cdp("Emulation.setDefaultBackgroundColorOverride", { color: { r: 0, g: 0, b: 0, a: 0 } });
// espera imagens e fontes carregarem
for (let i = 0; i < 60; i++) {
  const r = await cdp("Runtime.evaluate", { expression: "document.readyState==='complete' && [...document.images].every(i=>i.complete) && document.fonts.status==='loaded'", returnByValue: true });
  if (r.result?.result?.value) break;
  await espera(250);
}
await espera(300);
const n = Math.max(1, Math.round((t1 - t0) * fps));
for (let i = 0; i < n; i++) {
  const t = t0 + i / fps;
  const r0 = await cdp("Runtime.evaluate", { expression: `seek(${t})` });
  if (r0.result?.exceptionDetails) console.error("erro JS", JSON.stringify(r0.result.exceptionDetails).slice(0, 300));
  const r = await cdp("Page.captureScreenshot", fmt === "png" ? { format: "png", optimizeForSpeed: true } : { format: "jpeg", quality: 88, optimizeForSpeed: true });
  fs.writeFileSync(path.join(out, `f${String(i).padStart(4, "0")}.${fmt}`), Buffer.from(r.result.data, "base64"));
}
ws.close(); proc.kill();
await espera(500);
try { fs.rmSync(perfil, { recursive: true, force: true }); } catch { }
console.log("quadros", n);
