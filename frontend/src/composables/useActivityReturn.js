import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { examStore } from '@/stores/exam'

/**
 * Shared "Back to lesson" behaviour for the activity forms (Quiz/Exam/
 * Assignment/Discussion). When a form is opened from the lesson editor's
 * "create new" flow, examStore.returnContext is set. Once the activity has
 * been saved (getCreatedId() returns a name), clicking the button records a
 * pendingInsert and navigates back to the lesson, which splices the new
 * activity into its content.
 *
 * @param {() => (string|undefined)} getCreatedId returns the saved activity's name, if any
 */
export function useActivityReturn(getCreatedId) {
	const router = useRouter()
	const returnContext = computed(() => examStore.returnContext)
	const showBackToLesson = computed(() => !!returnContext.value)

	function backToLesson() {
		const ctx = returnContext.value
		if (!ctx) return
		const id = getCreatedId?.()
		if (id) {
			examStore.setPendingInsert({ type: ctx.insertType, id })
		}
		examStore.clearReturnContext()
		router.push(ctx.route)
	}

	return { showBackToLesson, backToLesson }
}
