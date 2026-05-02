const GREEN = new Set(['pass', 'passed', 'completed', 'paid', 'fulfilled', 'waived'])
const BLUE = new Set(['enrolled', 'in progress', 'submitted'])
const RED = new Set(['fail', 'failed', 'overdue'])
const ORANGE = new Set(['withdrawn', 'draft', 'pending', 'unpaid', 'not started', 'awaiting payment'])

export function statusTheme(status) {
	const s = (status || '').toString().trim().toLowerCase()
	if (GREEN.has(s)) return 'green'
	if (BLUE.has(s)) return 'blue'
	if (RED.has(s)) return 'red'
	if (ORANGE.has(s)) return 'orange'
	return 'gray'
}
