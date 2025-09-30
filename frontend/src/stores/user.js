import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'
import router from "@/router"

export const usersStore = defineStore('users', () => {
	let userResource = createResource({
		url: 'seminary.seminary.api.get_user_info',
		cache: "User",
		initialData: [],
		onSuccess: (data) => {
			console.log('User store: userResource loaded with data:', data)
		},
		onError(error) {
			console.log('User store error:', error)
			console.log("aasass")
			console.log(error.exc_type)
			if (error && error.exc_type === 'AuthenticationError') {
				router.push('/login')
			}
		},
		auto: true,
	})
	const allUsers = createResource({
		url: 'seminary.seminary.utils.get_all_users',
		cache: ['allUsers'],
	})
	return {
		userResource, allUsers
	}
})