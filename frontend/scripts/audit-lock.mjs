// Dependency vulnerability audit for this frontend.
//
// Why this exists: Yarn Classic (1.x) is EOL and its built-in `yarn audit`
// can no longer parse npm's advisory response — it throws
// "Unexpected audit response (Missing Metadata): false". `npm audit` is also
// unusable here because package.json carries a Yarn-only `link:../portal-shell`
// dependency that npm's resolver rejects. So we do what `yarn audit` does
// internally — parse yarn.lock and query npm's bulk advisory endpoint — without
// Yarn's broken response handling.
//
// Usage:  yarn audit:check     (or: node scripts/audit-lock.mjs [path/to/yarn.lock])
// Exit:   0 = clean, 1 = advisories found, 2 = error.
import { readFileSync } from 'node:fs'
import https from 'node:https'

const lockPath = process.argv[2] || new URL('../yarn.lock', import.meta.url).pathname

let text
try {
	text = readFileSync(lockPath, 'utf8')
} catch (e) {
	console.error(`Could not read lockfile at ${lockPath}: ${e.message}`)
	process.exit(2)
}

// Map package name -> set of installed versions, parsed from yarn.lock blocks.
const pkgs = new Map()
let currentNames = []
for (const raw of text.split('\n')) {
	if (!raw.trim() || raw.startsWith('#')) continue
	if (!raw.startsWith(' ')) {
		// Spec header: "a@range", "a@range2":  — strip the range, keep the name
		// (handles scoped names like "@scope/pkg@^1.0.0").
		currentNames = raw
			.replace(/:\s*$/, '')
			.split(',')
			.map((s) => s.trim().replace(/^"|"$/g, ''))
			.map((spec) => {
				const at = spec.lastIndexOf('@')
				return at > 0 ? spec.slice(0, at) : spec
			})
	} else {
		const m = raw.match(/^\s+version:?\s+"?([^"]+)"?\s*$/)
		if (m) {
			for (const name of currentNames) {
				if (!pkgs.has(name)) pkgs.set(name, new Set())
				pkgs.get(name).add(m[1])
			}
			currentNames = []
		}
	}
}

const body = {}
for (const [name, versions] of pkgs) body[name] = [...versions]
const payload = JSON.stringify(body)
console.log(`Auditing ${pkgs.size} packages from ${lockPath}…\n`)

const req = https.request(
	{
		method: 'POST',
		hostname: 'registry.npmjs.org',
		path: '/-/npm/v1/security/advisories/bulk',
		headers: {
			'Content-Type': 'application/json',
			'Content-Length': Buffer.byteLength(payload),
		},
	},
	(res) => {
		let data = ''
		res.on('data', (c) => (data += c))
		res.on('end', () => {
			if (res.statusCode !== 200) {
				console.error(`Registry returned HTTP ${res.statusCode}: ${data.slice(0, 200)}`)
				process.exit(2)
			}
			const advisories = JSON.parse(data)
			const names = Object.keys(advisories)
			if (!names.length) {
				console.log('✓ No known vulnerabilities found.')
				return
			}
			const sevRank = { critical: 4, high: 3, moderate: 2, low: 1, info: 0 }
			const counts = {}
			const rows = []
			for (const name of names) {
				for (const a of advisories[name]) {
					counts[a.severity] = (counts[a.severity] || 0) + 1
					rows.push({ name, ...a })
				}
			}
			rows.sort((a, b) => (sevRank[b.severity] || 0) - (sevRank[a.severity] || 0))
			for (const a of rows) {
				console.log(`[${a.severity.toUpperCase()}] ${a.name}  (vulnerable: ${a.vulnerable_versions})`)
				console.log(`    ${a.title}`)
				if (a.url) console.log(`    ${a.url}`)
				console.log()
			}
			const summary = Object.entries(counts)
				.sort((a, b) => (sevRank[b[0]] || 0) - (sevRank[a[0]] || 0))
				.map(([s, n]) => `${n} ${s}`)
				.join(', ')
			console.log(`— ${rows.length} advisory match(es): ${summary}`)
			process.exitCode = 1
		})
	}
)
req.on('error', (e) => {
	console.error('Request failed:', e.message)
	process.exit(2)
})
req.write(payload)
req.end()
