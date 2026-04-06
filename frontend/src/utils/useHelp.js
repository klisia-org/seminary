import { ref, watch, inject } from 'vue'
import { useRoute } from 'vue-router'
import { createResource } from 'frappe-ui'

export function useHelp() {
	const route = useRoute()
	const user = inject('$user')
	const helpData = ref(null)

	const helpResource = createResource({
		url: 'seminary.seminary.doctype.seminary_help_entry.seminary_help_entry.get_help_entry',
		onSuccess(data) {
			if (!data) {
				helpData.value = null
				return
			}
			// Hide from students if show_students is unchecked
			if (user.data?.is_student && !data.show_students) {
				helpData.value = null
				return
			}
			helpData.value = data
		},
		onError() {
			helpData.value = null
		},
	})

	watch(
		() => route.name,
		(pageName) => {
			if (pageName) {
				helpResource.submit({ frontend_page: pageName })
			} else {
				helpData.value = null
			}
		},
		{ immediate: true }
	)

	return { helpData }
}
