import { ref, unref, watch, computed } from 'vue'
import { createResource } from 'frappe-ui'

// The tax-ID field on the portal (ADR 071).
//
// Nothing here knows what a CPF is. It asks the server for the rule that
// applies to whichever country the record names and renders that — label,
// placeholder, mask, shape — so adding a country is one entry in `tax_ids.py`
// and no change in this file. Check digits are an algorithm rather than a
// pattern, so they stay on the server: the shape is checked as you type, and
// the checksum is confirmed on blur.

const RULES = {}

function ruleFor(country, subject) {
	const key = `${country || ''}|${subject || 'both'}`
	if (!RULES[key]) {
		RULES[key] = createResource({
			url: 'seminary.seminary.tax_ids.get_tax_id_rule',
			params: { country: country || '', subject: subject || 'both' },
			cache: ['tax_id_rule', key],
			auto: true,
		})
	}
	return RULES[key]
}

function clean(value, rule) {
	if (!value) return ''
	if (!rule?.configured) return String(value).trim()
	return String(value).replace(new RegExp(rule.clean, 'g'), '')
}

// The form a part-typed value is heading towards: the shortest one that could
// still hold it, so a Brazilian number masks as a CPF until the twelfth digit
// and as a CNPJ after it.
function formFor(cleaned, rule) {
	if (!rule?.configured || !rule.forms?.length) return null
	const byLength = [...rule.forms].sort(
		(a, b) => (a.mask || '').length - (b.mask || '').length,
	)
	return (
		byLength.find(
			(f) => (f.mask || '').split('#').length - 1 >= cleaned.length,
		) || byLength[byLength.length - 1]
	)
}

function applyMask(cleaned, form) {
	if (!form?.mask) return cleaned
	let out = ''
	let i = 0
	for (const char of form.mask) {
		if (char === '#') {
			if (i >= cleaned.length) break
			out += cleaned[i++]
		} else if (i < cleaned.length) {
			out += char
		}
	}
	return out
}

/**
 * @param {import('vue').Ref<string>|string} country  reactive: the rule follows
 *   whatever country the form currently names.
 * @param {object} [options]
 * @param {string} [options.subject]  'person' or 'organization'
 */
export function useTaxId(country, options = {}) {
	const subject = options.subject || 'both'
	const rule = ref({ configured: false })
	const error = ref('')

	function load() {
		const resource = ruleFor(unref(country), subject)
		// A cached resource already has data and no pending promise; a fresh one
		// has the promise and nothing else. Handle both without assuming either.
		if (resource.data) rule.value = resource.data
		error.value = ''
		Promise.resolve(resource.promise)
			.then(() => {
				rule.value = resource.data || { configured: false }
			})
			.catch(() => {
				rule.value = { configured: false }
			})
	}

	watch(() => unref(country), load, { immediate: true })

	const label = computed(() => rule.value?.label || 'Tax ID')
	const note = computed(() => rule.value?.note || '')
	const placeholder = computed(() => rule.value?.forms?.[0]?.example || '')

	/** Mask a value for display, as the user types. */
	function format(value) {
		const cleaned = clean(value, rule.value)
		return applyMask(cleaned, formFor(cleaned, rule.value))
	}

	/**
	 * Shape now, check digits on the server. Resolves to '' when the value is
	 * fine, and sets `error` either way so a caller can just read it.
	 */
	async function validate(value) {
		error.value = ''
		if (!value || !rule.value?.configured) return ''

		const cleaned = clean(value, rule.value)
		const shapeOk = rule.value.forms.some((f) =>
			new RegExp(f.pattern).test(cleaned),
		)
		if (!shapeOk) {
			const names = rule.value.forms.map((f) => f.name).join(' / ')
			error.value = `That does not look like a ${names}.`
			return error.value
		}

		try {
			const checker = createResource({
				url: 'seminary.seminary.tax_ids.check_tax_id',
			})
			const verdict = (await checker.submit({
				value,
				country: unref(country) || '',
				subject,
			})) || checker.data
			if (verdict && !verdict.ok) error.value = verdict.message || ''
		} catch (e) {
			// An unreachable endpoint must not block the form; the server
			// refuses the save either way.
		}
		return error.value
	}

	return { rule, label, note, placeholder, error, format, validate }
}
