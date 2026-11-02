// Render every ```mermaid block in the given Markdown files with mermaid.js in Chromium and
// report syntax errors (GitHub renders the same syntax).  node tools/check-mermaid.cjs ../docs/*.md
const fs = require("node:fs");
const { chromium } = require("@playwright/test");

(async () => {
  const blocks = [];
  for (const file of process.argv.slice(2)) {
    const text = fs.readFileSync(file, "utf8");
    for (const m of text.matchAll(/```mermaid\r?\n([\s\S]*?)```/g)) blocks.push({ file, src: m[1] });
  }
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.setContent("<html><body></body></html>");
  await p.addScriptTag({ url: "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js" });
  let bad = 0;
  for (const [i, blk] of blocks.entries()) {
    const err = await p.evaluate(async ({ src, i }) => {
      try {
        window.mermaid.initialize({ startOnLoad: false });
        await window.mermaid.render(`d${i}`, src);
        return null;
      } catch (e) {
        return String(e.message || e).slice(0, 300);
      }
    }, { src: blk.src, i });
    if (err) {
      bad++;
      console.log(`FAIL ${blk.file} #${i}: ${err}`);
    }
  }
  console.log(`${blocks.length} diagrams, ${bad} failed`);
  await b.close();
  process.exit(bad ? 1 : 0);
})();
