// Checks a HyperFrames composition every 0.1 s and lists the elements that overlap on screen (and, with --face,
// the elements that cover the face in the video). Called by `reel.py overlaps`; module 'graphics'.
//
//   node overlaps.mjs <graphics-dir> <chrome> <composition dir | index.html> [--step 0.1] [--face face.json]
//
// What counts as an element: everything marked data-check="name" when the composition has any; otherwise every
// visible leaf with text, plus img/svg/video/canvas, ignoring anything that covers more than half the frame
// (backgrounds) and the video itself. A visible element is one whose clips are active (data-start/data-duration)
// and whose accumulated opacity is above 0.05. Exit 1 when something overlaps.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const [graphicsDir, chrome, target, ...rest] = process.argv.slice(2);
if (!target) {
  console.error('usage: overlaps.mjs <graphics-dir> <chrome> <composition> [--step 0.1] [--face face.json]');
  process.exit(2);
}
const opt = (name, def) => {
  const i = rest.indexOf(name);
  return i >= 0 ? rest[i + 1] : def;
};
const step = Number(opt('--step', '0.1'));
const facePath = opt('--face', null);
const face = facePath ? JSON.parse(fs.readFileSync(facePath, 'utf8')) : null;
let file = path.resolve(target);
if (fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');

const require = createRequire(path.join(graphicsDir, 'package.json'));
const puppeteer = require('puppeteer-core');

const browser = await puppeteer.launch({
  executablePath: chrome, headless: true, args: ['--allow-file-access-from-files'],
});
const page = await browser.newPage();
page.on('pageerror', (e) => console.error('page error:', e.message));
await page.evaluateOnNewDocument(() => { window.__timelines = {}; });
await page.goto(pathToFileURL(file).href, { waitUntil: 'load' });
const size = await page.evaluate(() => {
  const root = document.querySelector('[data-composition-id]');
  return { w: Number(root?.dataset.width || 1080), h: Number(root?.dataset.height || 1920) };
});
await page.setViewport({ width: size.w, height: size.h });
for (let i = 0; !(await page.evaluate(() => Object.keys(window.__timelines || {}).length > 0)); i++) {
  if (i > 100) throw new Error('the composition did not register a timeline (window.__timelines)');
  await new Promise((r) => setTimeout(r, 100));
}

const hits = await page.evaluate((step, face) => {
  const root = document.querySelector('[data-composition-id]');
  const tl = window.__timelines[root?.dataset.compositionId] || Object.values(window.__timelines)[0];
  tl.pause();
  const dur = Math.max(tl.duration(), Number(root?.dataset.duration || 0));
  const W = innerWidth, H = innerHeight;
  const marked = [...document.querySelectorAll('[data-check]')];
  const leafText = (el) => [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
  const items = (marked.length ? marked : [...root.querySelectorAll('*')].filter((el) =>
    ['IMG', 'SVG', 'svg', 'CANVAS'].includes(el.tagName) || leafText(el)))
    .filter((el) => el.tagName !== 'VIDEO' && el.tagName !== 'SCRIPT' && el.tagName !== 'STYLE')
    .map((el) => ({
      el,
      name: el.dataset.check || (el.id ? `#${el.id}` : '') || `${el.tagName.toLowerCase()}${el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/)[0] : ''}`
        + (leafText(el) ? ` "${el.textContent.trim().slice(0, 24)}"` : ''),
    }));
  const active = (el, t) => {
    for (let c = el.closest('[data-start]'); c; c = c.parentElement?.closest('[data-start]')) {
      const s = +c.dataset.start, d = +(c.dataset.duration ?? Infinity);
      if (!(t >= s && t < s + d)) return false;
    }
    return true;
  };
  const alpha = (el) => {
    let a = 1;
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.display === 'none' || cs.visibility === 'hidden') return 0;
      a *= +cs.opacity;
    }
    return a;
  };
  const out = {};
  for (let t = 0; t < dur; t += step) {
    tl.seek(t, false);
    const vis = items.filter((it) => active(it.el, t) && alpha(it.el) > 0.05)
      .map((it) => ({ ...it, r: it.el.getBoundingClientRect() }))
      .filter((it) => it.r.width > 0 && it.r.height > 0 && it.r.width * it.r.height < 0.5 * W * H);
    if (face) {
      const m = face.samples[Math.min(face.samples.length - 1, Math.round(t / face.step))];
      const sx = W / face.w, sy = H / face.h;
      if (m && Math.abs(m.t - t) <= face.step) for (const c of m.faces) {
        vis.push({ name: 'FACE (video)', el: null, r: { left: c.box[0] * sx, top: c.box[1] * sy, right: c.box[2] * sx, bottom: c.box[3] * sy } });
      }
    }
    for (let i = 0; i < vis.length; i++) {
      for (let j = i + 1; j < vis.length; j++) {
        const a = vis[i], b = vis[j];
        if (a.el && b.el && (a.el.contains(b.el) || b.el.contains(a.el))) continue;  // a card and its own text
        const w = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left);
        const h = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
        if (w > 4 && h > 4) (out[[a.name, b.name].sort().join(' × ')] ||= []).push(Math.round(t * 10) / 10);
      }
    }
  }
  return out;
}, step, face);
await browser.close();

const lines = Object.entries(hits).map(([k, ts]) => {
  const spans = [];
  for (const t of ts) {
    const last = spans[spans.length - 1];
    if (last && t - last[1] <= step * 1.5 + 1e-9) last[1] = t; else spans.push([t, t]);
  }
  return `  x ${k}: ` + spans.map(([a, b]) => (a === b ? `${a.toFixed(1)} s` : `${a.toFixed(1)}–${b.toFixed(1)} s`)).join(', ');
});
console.log(lines.length ? `Overlaps (${lines.length}):\n${lines.join('\n')}` : 'No overlaps.');
process.exit(lines.length ? 1 : 0);
