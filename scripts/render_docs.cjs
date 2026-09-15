// Optional offline documentation renderer. Algorithm and GUI do not need Node.
// npm install --prefix scripts/docs_renderer
// node scripts/render_docs.cjs
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const modules = path.resolve(process.argv[2] || path.join(__dirname, 'docs_renderer'));
const katex = require(path.join(modules, 'node_modules/katex'));
const MarkdownIt = require(path.join(modules, 'node_modules/markdown-it'));
const texmath = require(path.join(modules, 'node_modules/markdown-it-texmath'));
const md = new MarkdownIt({html:false, linkify:true, typographer:false}).use(texmath, {
  engine: katex, delimiters: 'dollars',
  katexOptions: {throwOnError:true, strict:'ignore', trust:false}
});
const assets = path.join(root, 'docs/_static/katex');
fs.mkdirSync(assets, {recursive:true});
const dist = path.join(modules, 'node_modules/katex/dist');
fs.copyFileSync(path.join(dist, 'katex.min.css'), path.join(assets, 'katex.min.css'));
fs.cpSync(path.join(dist, 'fonts'), path.join(assets, 'fonts'), {recursive:true});
fs.copyFileSync(path.join(modules, 'node_modules/katex/LICENSE'), path.join(assets, 'LICENSE'));
const report = {};
for (const name of ['USER_GUIDE', 'TECHNICAL_METHODS']) {
  const src = fs.readFileSync(path.join(root, 'docs', name+'.md'), 'utf8');
  const text = src.replace(/```[\s\S]*?```/g, '').replace(/`[^`\n]+`/g, '');
  const display = [...text.matchAll(/\$\$([\s\S]*?)\$\$/g)].map(m=>m[1]);
  const noDisplay = text.replace(/\$\$[\s\S]*?\$\$/g, '');
  const inline = [...noDisplay.matchAll(/(?<![\\$])\$(?!\$)([^$\n]+?)\$(?!\$)/g)].map(m=>m[1]);
  for (const expr of [...display, ...inline]) {
    katex.renderToString(expr, {throwOnError:true, strict:'ignore', trust:false});
  }
  const body = md.render(src).replace(/href="(USER_GUIDE|TECHNICAL_METHODS)\.md/g, 'href="$1.html')
    .replace(/<pre><code class="language-mermaid">[\s\S]*?<\/code><\/pre>/g,
      '<figure><img style="width:100%;height:auto" src="_static/pipeline.svg" alt="根系量化流程：分割、骨架、路径图、测量和质量控制"></figure>');
  if (/katex-error|class="texerror"/.test(body)) throw new Error('Math rendering error in '+name);
  const title = name==='USER_GUIDE' ? '软件详细使用指南' : '算法技术方案与数学公式';
  const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>${title} · V1.0.0</title>
<link rel="stylesheet" href="_static/katex/katex.min.css"><style>
body{max-width:1120px;margin:36px auto;padding:0 30px;color:#17212b;font:16px/1.8 'Microsoft YaHei','PingFang SC',sans-serif}
h1,h2,h3{line-height:1.35}h2{margin-top:2.3em;border-bottom:1px solid #cad6df;padding-bottom:10px}
table{border-collapse:collapse;width:100%;display:block;overflow:auto;font-size:14px}td,th{border:1px solid #ccd6df;padding:8px 12px;text-align:left}th{background:#edf3f7}
code,pre{font-family:Consolas,monospace;background:#f2f5f8}pre{padding:16px;overflow:auto;line-height:1.5}code{padding:1px 4px}a{color:#0067ad}
.katex-display{overflow-x:auto;overflow-y:hidden;padding:12px 0}eqn{display:block;overflow-x:auto;padding:12px 0}blockquote{border-left:4px solid #789;padding-left:18px}
nav{background:#edf3f7;padding:12px 18px}@media print{body{margin:0;padding:0;font-size:10pt}pre,table{white-space:pre-wrap}nav{display:none}h2,h3{break-after:avoid}}
</style></head><body><nav><a href="USER_GUIDE.html">使用指南</a> · <a href="TECHNICAL_METHODS.html">技术方案与公式</a> · <a href="${name}.md">Markdown 原文</a></nav>${body}</body></html>`;
  fs.writeFileSync(path.join(root, 'docs', name+'.html'), html, 'utf8');
  report[name]={display_equations:display.length, inline_equations:inline.length,
    rendered_math_nodes:(body.match(/class="katex"/g)||[]).length, validation:'pass'};
}
fs.writeFileSync(path.join(root, 'docs/FORMULA_RENDER_CHECK.json'), JSON.stringify({
  renderer:'KaTeX',version:katex.version,offline:true,documents:report},null,2)+'\n');
console.log(JSON.stringify(report));
