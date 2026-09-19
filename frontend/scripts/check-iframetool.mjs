/**
 * p008 F4 (p005a A05-10): the IframeEmbed EditorJS tool takes a URL from the
 * author's input and nothing else. Runs the REAL tool under jsdom.
 *
 * Needs jsdom, deliberately not a dependency -- run from a directory that has it
 * (see check-sanitize.mjs for the two-line setup).
 */
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const here = path.dirname(fileURLToPath(import.meta.url))
let JSDOM
try {
	;({ JSDOM } = createRequire(path.join(process.cwd(), 'x.js'))('jsdom'))
} catch {
	console.error('jsdom not found from ' + process.cwd() + ' -- see check-sanitize.mjs.')
	process.exit(2)
}
const dom = new JSDOM('<!doctype html><body></body>', { url: 'https://school.example/seminary/x' })
globalThis.window = dom.window; globalThis.document = dom.window.document
globalThis.DOMParser = dom.window.DOMParser; globalThis.__ = (s) => s
// navigator is a read-only getter in node 24
globalThis.SVGElement = dom.window.SVGElement; globalThis.Element = dom.window.Element
const { IframeEmbed } = await import(path.join(here, '..', 'src', 'utils', 'iframetool.js'))
let fail = 0
const must = (l, ok, got) => { if (!ok) { fail++; console.log('  FAIL', l, '->', got) } else console.log('  ok  ', l) }
const E = (v) => IframeEmbed.embedUrl(v)
must('bare https URL', E('https://view.genially.com/abc') === 'https://view.genially.com/abc', E('https://view.genially.com/abc'))
must('iframe snippet -> src only', E('<iframe src="https://h5p.org/h5p/embed/1" onload="alert(1)" width="9"></iframe>') === 'https://h5p.org/h5p/embed/1')
must('div-wrapped iframe -> src only', E('<div onmouseover="x()"><iframe src="https://docs.google.com/x"></iframe></div>') === 'https://docs.google.com/x')
must('div with handler, no iframe -> nothing', E('<div><img src=x onerror=alert(1)></div>') === '')
must('javascript: src refused', E('<iframe src="javascript:alert(1)"></iframe>') === '')
must('data: src refused', E('<iframe src="data:text/html,<script>1</script>"></iframe>') === '')
must('same-origin src refused', E('<iframe src="https://school.example/files/evil.html"></iframe>') === '')
must('relative src refused', E('<iframe src="/files/evil.html"></iframe>') === '')
must('protocol-relative refused', E('//evil.example/x') === '')
must('srcdoc-only iframe refused', E('<iframe srcdoc="<script>1</script>"></iframe>') === '')
must('empty', E('') === '' && E(null) === '')
// the parse itself must not execute or load anything
let fired = false; dom.window.alert = () => { fired = true }
E('<iframe src="https://ok.example"></iframe><img src=x onerror="alert(1)"><script>alert(1)</script>')
must('parsing a hostile snippet runs nothing', fired === false)
const el = IframeEmbed.buildEmbed('https://ok.example/e')
const fr = el.querySelector('iframe')
must('built iframe carries only the checked src', fr.getAttribute('src') === 'https://ok.example/e' && !fr.hasAttribute('onload') && !fr.hasAttribute('srcdoc'))
const tool = new IframeEmbed({ data: { html: '<div onclick="x"><iframe src="https://ok.example/e" onload="y"></iframe></div>' }, readOnly: true })
const out = tool.render()
must('read-only render: one clean iframe, no handlers anywhere', out.querySelectorAll('iframe').length === 1 && !/onclick|onload/.test(out.innerHTML), out.innerHTML)
const bad = new IframeEmbed({ data: { html: '<div><img src=x onerror=alert(1)></div>' }, readOnly: true })
must('read-only render of a hostile block: nothing at all', bad.render().innerHTML === '', bad.render().innerHTML)
must('save() stores the bare URL', new IframeEmbed({ data: { html: '<iframe src="https://ok.example/e" onload=1></iframe>' } }).save().html === 'https://ok.example/e')
must('save sanitizer keeps no tags', JSON.stringify(IframeEmbed.sanitize) === '{"html":false}')
console.log(fail ? `\n${fail} FAILED` : '\nALL PASSED'); process.exit(fail ? 1 : 0)
