// Renders lib/mock/samples.json into thermal-receipt PNGs (public/samples/<key>.png).
// Each line is 18px tall at 1x with 20px top padding, so a field on line i sits at y = 40 + 36i in the 2x image.
// Usage: node scripts/render-samples.mjs <path to hallmark capture.mjs>
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync, renameSync, rmSync } from "node:fs";
import { join } from "node:path";

const capture = process.argv[2];
const samples = JSON.parse(readFileSync("lib/mock/samples.json", "utf8"));
const tmp = join("scripts", ".render");
mkdirSync(tmp, { recursive: true });
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");

for (const s of samples) {
  const rows = s.lines
    .map((l) => {
      const b = l.b ? ' style="font-weight:600"' : "";
      if (l.c) return `<p class="c"${b}>${esc(l.c)}</p>`;
      if (l.t) return `<p class="r"${b}><span>${esc(l.t).replace(/^ /, "&nbsp;")}</span><span>${esc(l.r ?? "")}</span></p>`;
      return '<div class="g"></div>';
    })
    .join("\n");
  const blur = s.blurry ? "filter:blur(0.35px) contrast(0.92);" : "";
  const html = `<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Azeret+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>body{margin:0;padding:40px;background:#edf7eb}.receipt{width:236px;background:#f7f6f2;color:#3a3936;font:11.5px/18px "Azeret Mono",monospace;padding:20px 16px 24px;${blur}}
p{margin:0;white-space:nowrap;height:18px}.c{text-align:center}.r{display:flex;justify-content:space-between}.g{height:18px}</style></head>
<body><div class="receipt" id="r">${rows}</div></body></html>`;
  writeFileSync(join(tmp, `${s.key}.html`), html);
  execFileSync("node", [capture, join(tmp, `${s.key}.html`), "--selector", "#r", "--scale", "2", "--out", tmp, "--name", s.key, "--sizes", "desktop"], { stdio: "ignore" });
  renameSync(join(tmp, `${s.key}-home-desktop-part.png`), join("public", "samples", `${s.key}.png`));
}
rmSync(tmp, { recursive: true, force: true });
console.log("rendered", samples.map((s) => s.key).join(", "));
