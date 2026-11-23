import { onBeforeUnmount, ref, watch } from 'vue'
import { checkHtml } from '@/utils/contentCheck'

/**
 * The accessibility checker for a rich-text field (102 §7).
 *
 * `source` returns the field's HTML. `issues` follows it a moment after the
 * instructor stops typing; bind `checker` as the ref of a <ContentIssues> and
 * await `confirmSave()` before saving: it resolves false only when the
 * instructor chose to go back and fix. It warns; it never blocks.
 */
export function useContentCheck(source, { delay = 800 } = {}) {
	const checker = ref(null)
	const issues = ref([])
	let timer

	const run = () => {
		clearTimeout(timer)
		issues.value = checkHtml(source() || '')
	}

	watch(source, () => {
		clearTimeout(timer)
		timer = setTimeout(run, delay)
	}, { immediate: true })

	onBeforeUnmount(() => clearTimeout(timer))

	const confirmSave = async () => {
		run()
		if (!checker.value) return true
		return checker.value.confirm(issues.value)
	}

	return { checker, issues, confirmSave }
}
