import { MessagesSquare } from 'lucide-vue-next'
import { createApp, h } from 'vue'
import AssessmentPlugin from '@/components/AssessmentPlugin.vue'
import DiscussionActivityBlock from '@/components/DiscussionActivityBlock.vue'
import translationPlugin from '../translation'
import { usersStore } from '@/stores/user'
import router from '../router'

export class DiscussionActivity {
	constructor({ data, api, readOnly, config }) {
		this.data = data
		this.readOnly = readOnly
		this.course = config?.course || null  // capture course from config
		this.courseName = config?.courseName || null
		console.log('DiscussionActivity tool initialized with course:', this.course) // Debugging
	}

	static get toolbox() {
		const app = createApp({
			render: () =>
				h(MessagesSquare, { size: 18, strokeWidth: 1.5, color: 'black' }),
		})

		const div = document.createElement('div')
		app.mount(div)

		return {
			title: __('Discussion Activity'),
			icon: div.innerHTML,
		}
	}

	static get isReadOnlySupported() {
		return true
	}

	render() {
		this.wrapper = document.createElement('div')
		if (Object.keys(this.data).length) {
			this.renderDiscussionActivity(this.data.discussion)
		} else {
			this.renderDiscussionActivityModal()
		}
		return this.wrapper
	}

	renderDiscussionActivity(discussion) {
		if (!discussion) {
			console.warn('[DiscussionActivity] Missing discussion id; falling back to selector')
			this.renderDiscussionActivityModal()
			return
		}
		if (this.readOnly) {
			// Get courseName from the current route
           
			console.log('Rendering DiscussionActivity in read-only mode for discussion:', discussion, 'in course:', this.courseName) // Debugging
			const app = createApp(DiscussionActivityBlock, {
				discussionID: discussion,
				courseName: this.courseName,  // Pass courseName to the block component
			})
			app.use(translationPlugin)
			app.
			app.use(router)
			const { userResource } = usersStore()
			app.provide('$user', userResource)
			app.mount(this.wrapper)
			return
		}
		this.wrapper.innerHTML = `<div class='border rounded-md p-10 text-center bg-surface-menu-bar mb-2'>
            <span class="font-medium">
                Discussion Activity: ${discussion}
            </span>
        </div>`
		return
	}

	renderDiscussionActivityModal() {
		if (this.readOnly) {
			return
		}
		const app = createApp(AssessmentPlugin, {
			type: 'discussionactivity',
			course: this.course,  // pass course to the modal component
			onAddition: (discussion) => {
				this.data.discussion = discussion
				this.renderDiscussionActivity(discussion)
			},

		})
		app.use(translationPlugin)
		app.use(router) // Explicitly provide the router
		app.mount(this.wrapper)
	}

		save(blockContent) {
		return {
			discussion: this.data.discussion,
		}
	}
}
