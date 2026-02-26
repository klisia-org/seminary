import { Pencil } from 'lucide-vue-next'
import { createApp, h } from 'vue'
import AssessmentPlugin from '@/components/AssessmentPlugin.vue'
import AssignmentBlock from '@/components/AssignmentBlock.vue'
import translationPlugin from '../translation'
import { usersStore } from '@/stores/user'
import router from '../router'

export class Assignment {
	constructor({ data, api, readOnly, config }) {
		this.data = data
		this.readOnly = readOnly
		this.course = config?.course || null  // capture course from config
		console.log('Assignment tool initialized with course:', this.course) // Debugging
	}

	static get toolbox() {
		const app = createApp({
			render: () =>
				h(Pencil, { size: 18, strokeWidth: 1.5, color: 'black' }),
		})

		const div = document.createElement('div')
		app.mount(div)

		return {
			title: __('Assignment'),
			icon: div.innerHTML,
		}
	}

	static get isReadOnlySupported() {
		return true
	}

	render() {
		this.wrapper = document.createElement('div')
		if (Object.keys(this.data).length) {
			this.renderAssignment(this.data.assignment)
		} else {
			this.renderAssignmentModal()
		}
		return this.wrapper
	}

	renderAssignment(assignment) {
		if (this.readOnly) {
			const app = createApp(AssignmentBlock, {
				assignmentID: assignment,
			})
			app.use(translationPlugin)
			app.use(router)
			const { userResource } = usersStore()
			app.provide('$user', userResource)
			app.mount(this.wrapper)
			return
		}
		this.wrapper.innerHTML = `<div class='border rounded-md p-10 text-center bg-surface-menu-bar mb-2'>
            <span class="font-medium">
                Assignment: ${assignment}
            </span>
        </div>`
		return
	}

	renderAssignmentModal() {
		if (this.readOnly) {
			return
		}
		const app = createApp(AssessmentPlugin, {
			type: 'assignment',
			course: this.course,  // pass course to the modal component
			onAddition: (assignment) => {
				this.data.assignment = assignment
				this.renderAssignment(assignment)
			},

		})
		app.use(translationPlugin)
		app.use(router) // Explicitly provide the router
		app.mount(this.wrapper)
	}

	save(blockContent) {
		return {
			assignment: this.data.assignment,
		}
	}
}
