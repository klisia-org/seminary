/**
 * p008 F1: run the REAL client HTML policy (src/utils/sanitize.js, htmlPolicy.js,
 * urlPolicy.js) against a corpus -- attacks that must not survive, and authored
 * formatting that must (tables, floats, RTL Hebrew, polytonic Greek, pasted
 * images).
 *
 * Needs jsdom, which is deliberately NOT a dependency of this project. Run it
 * from any directory that has jsdom installed, e.g.
 *
 *     mkdir -p /tmp/purify && cd /tmp/purify && npm i jsdom
 *     node /path/to/frontend/scripts/check-sanitize.mjs
 *
 * DOMPurify itself is taken from this project's node_modules, so the version
 * under test is the one that ships.
 */
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const here = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.join(here, '..', 'src', 'utils') + path.sep
let JSDOM
try {
	;({ JSDOM } = createRequire(path.join(process.cwd(), 'x.js'))('jsdom'))
} catch {
	console.error('jsdom not found from ' + process.cwd() + ' -- see the header of this file.')
	process.exit(2)
}
const createDOMPurify = createRequire(path.join(here, '..', 'x.js'))('dompurify')
const { PROFILES, installHooks } = await import(SRC + 'sanitize.js')
const { safeUrl, safeEmbedUrl } = await import(SRC + 'urlPolicy.js')

const purify = createDOMPurify(new JSDOM('').window)
installHooks(purify)
const clean = (html, profile = 'rich') => purify.sanitize(html, PROFILES[profile])

let fail = 0
const must = (label, ok, got) => { if (!ok) { fail++; console.log('  FAIL', label, '\n       ->', got) } else console.log('  ok  ', label) }

console.log('--- attacks that must not survive (rich) ---')
const kill = [
  ['script tag', '<script>alert(1)</script>x', /<script|alert/],
  ['img onerror', '<img src=x onerror=alert(1)>', /onerror/],
  ['p005 comment bypass', '<!--><img src=x onerror=alert(1)>-->', /onerror/],
  ['svg onload', '<svg onload=alert(1)><circle r=1/></svg>', /onload|<svg/],
  ['credential form', '<form action="//evil"><input name=u><button>Login</button></form>', /<form|<input|<button/],
  ['fixed overlay', '<div style="position:fixed;top:0;left:0;width:100%;height:100%;z-index:9999">x</div>', /position|z-index|top:|left:/],
  ['inset overlay', '<div style="position:absolute;inset:0">x</div>', /inset|position/],
  ['style element', '<style>body{display:none}</style>x', /<style/],
  ['iframe', '<iframe src="https://evil"></iframe>', /<iframe/],
  ['javascript href', '<a href="javascript:alert(1)">x</a>', /javascript:/],
  ['data html href', '<a href="data:text/html,<script>1</script>">x</a>', /data:text/],
  ['style url() beacon', '<p style="background-image:url(https://evil/b.png)">x</p>', /url\(/],
  ['base tag', '<base href="https://evil/">x', /<base/],
  ['meta refresh', '<meta http-equiv="refresh" content="0;url=https://evil">x', /<meta/],
  ['math/mtext mutation', '<math><mtext><style><img src=x onerror=alert(1)></style></mtext></math>', /onerror|<math/],
  ['srcdoc', '<iframe srcdoc="<script>1</script>"></iframe>', /srcdoc|<iframe/],
  ['data- attr', '<p data-x="1">x</p>', /data-x/],
]
for (const [label, html, bad] of kill) { const out = clean(html); must(label, !bad.test(out), out) }

console.log('--- formatting that must survive byte-meaningfully (rich) ---')
const keep = [
  ['table with widths', '<table style="width: 80%"><tbody><tr><td colspan="2" style="text-align: center">a</td></tr></tbody></table>', ['<table', 'width: 80%', 'colspan="2"', 'text-align: center']],
  ['floated sized image', '<img src="/files/a.png" alt="a" width="200" style="float: left; margin-right: 8px">', ['<img', 'float: left', 'margin-right: 8px', 'width="200"', 'src="/files/a.png"']],
  ['private file image', '<img src="/private/files/a.png?fid=abc">', ['/private/files/a.png?fid=abc']],
  ['pointed Hebrew RTL', '<span dir="rtl" lang="he">בְּרֵאשִׁית</span>', ['dir="rtl"', 'lang="he"', 'בְּרֵ']],
  ['polytonic Greek', '<p>Ἐν ἀρχῇ ἦν ὁ λόγος</p>', ['Ἐν ἀρχῇ']],
  ['centered paragraph', '<p style="text-align: center; color: rgb(200, 0, 0)">x</p>', ['text-align: center', 'color: rgb(200, 0, 0)']],
  ['sup/sub/abbr/blockquote', '<blockquote cite="https://x.y">q</blockquote><abbr title="t">a</abbr><sup>1</sup><sub>2</sub>', ['<blockquote', 'cite=', '<abbr title="t"', '<sup>', '<sub>']],
  ['lists + headings', '<h2>T</h2><ol><li>a</li></ol><ul><li>b</li></ul>', ['<h2>', '<ol>', '<ul>']],
  ['external link w/ target', '<a href="https://ok.example" target="_blank">x</a>', ['href="https://ok.example"', 'target="_blank"', 'rel="noopener noreferrer"']],
  ['mailto + relative', '<a href="mailto:a@b.c">m</a><a href="/seminary/courses">r</a>', ['mailto:a@b.c', '/seminary/courses']],
  ['display + border', '<div style="display: flex; border: 1px solid #ccc; padding: 4px">x</div>', ['display: flex', 'border: 1px solid', 'padding: 4px']],
]
for (const [label, html, needles] of keep) { const out = clean(html); must(label, needles.every((n) => out.includes(n)), out) }

console.log('--- profiles ---')
let o = clean('<svg viewBox="0 0 24 24"><path d="M1 1h2"/><script>1</script><foreignObject><img src=x onerror=1></foreignObject><use href="#x"/></svg>', 'svg')
must('svg keeps path, drops script/foreignObject/use', o.includes('<path') && !/script|foreignObject|onerror|<use/.test(o), o)
o = clean('<span class="hljs-keyword">def</span> f():<br><img src=x onerror=1><div onclick="x">y</div>', 'code')
must('code keeps hljs spans + breaks, drops img and handlers', o.includes('hljs-keyword') && o.includes('<br>') && !/img|onclick|onerror/.test(o), o)
o = clean('<p>block</p><b>b</b><a href="javascript:1">x</a><img src=x>', 'inline')
must('inline drops block tags/img, keeps <b>', o.includes('<b>b</b>') && !/<p>|<img|javascript/.test(o), o)
o = clean('<p><img src="data:image/png;base64,iVBORw0KGgo="><a href="javascript:alert(1)">l</a></p>', 'docx')
must('docx keeps data:image, drops javascript: link', o.includes('data:image/png') && !/javascript/.test(o), o)
o = clean('<img src="data:image/png;base64,iVBORw0KGgo=">', 'rich')
must('rich keeps a pasted data: image (editor paste) ', /data:image\/png/.test(o), o)
o = clean('<img src="data:image/svg+xml,<svg onload=alert(1)>">', 'rich')
must('...and a data: svg in <img> carries no handler out', !/onload="/.test(o.replace(/src="[^"]*"/, '')), o)

console.log('--- safeUrl ---')
const NL = String.fromCharCode(10), TAB = String.fromCharCode(9)
const urls = [
  ['https://ok.example/a?b=1', 'https://ok.example/a?b=1'], ['mailto:a@b.c', 'mailto:a@b.c'], ['tel:+15551234', 'tel:+15551234'],
  ['/files/x.pdf', '/files/x.pdf'], ['#frag', '#frag'], ['?q=1', '?q=1'],
  ['javascript:alert(1)', ''], ['JaVaScRiPt:alert(1)', ''], ['java' + NL + 'script:alert(1)', ''], [TAB + 'javascript:alert(1)', ''],
  ['data:text/html,x', ''], ['vbscript:x', ''], ['//evil.example', ''], ['\\\\evil', ''], ['', ''], [null, ''],
]
for (const [inp, want] of urls) must('safeUrl ' + JSON.stringify(inp), safeUrl(inp) === want, safeUrl(inp))
must('safeEmbedUrl other origin', safeEmbedUrl('https://view.genially.com/x', 'https://school.example') === 'https://view.genially.com/x')
must('safeEmbedUrl refuses same origin', safeEmbedUrl('https://school.example/files/x.html', 'https://school.example') === '')
must('safeEmbedUrl refuses relative', safeEmbedUrl('/files/x.html', 'https://school.example') === '')
must('safeEmbedUrl refuses javascript:', safeEmbedUrl('javascript:alert(1)', 'https://school.example') === '')
console.log(fail ? `\n${fail} FAILED` : '\nALL PASSED')
process.exit(fail ? 1 : 0)
