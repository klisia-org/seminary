import { computed, toValue } from 'vue'
import { useRoute, useRouter } from 'vue-router'

/**
 * Keep a page's active tab in `?tab=` (ADR 075).
 *
 * Before this, four pages read a query param once on mount and never wrote
 * back, so a reload or a pasted link silently dropped you on the first tab.
 *
 * `replace`, not `push`: flipping tabs should not bury the page the user
 * arrived from under a stack of history entries. The tab is still restored on
 * reload and still travels in a shared link — it just isn't a navigation step.
 *
 * Both `keys` and `fallback` accept refs/getters as well as plain values, so a
 * page whose tab set depends on loaded data (Faculty Worklist's queues) can pass
 * computeds and have the fallback re-resolve as the data arrives.
 *
 * @param {string[]|import('vue').Ref} keys      valid tab keys, in order
 * @param {string|import('vue').Ref}   fallback  key when the param is absent or unknown
 * @param {string}   param  query key, so a page with two independent tab rows
 *                          can use different ones
 */
export function useTabParam(keys, fallback, param = 'tab') {
	const route = useRoute()
	const router = useRouter()

	return computed({
		get() {
			const v = route.query[param]
			// An unknown value falls back rather than rendering an empty page --
			// a stale or hand-edited link should land somewhere real.
			return toValue(keys).includes(v) ? v : toValue(fallback)
		},
		set(value) {
			if (!toValue(keys).includes(value)) return
			// Preserve every other param: ?tab= shares the query string with
			// ?project=, ?cohort=, ?compose= and friends.
			const query = { ...route.query, [param]: value }
			// The fallback is the clean URL, so the default tab doesn't leave a
			// param behind on every link the user copies.
			if (value === toValue(fallback)) delete query[param]
			router.replace({ query })
		},
	})
}
