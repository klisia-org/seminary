import { MessagesSquare } from 'lucide-vue-next'
import { createApp, h } from 'vue'
import AssessmentPlugin from '@/components/AssessmentPlugin.vue'
import DiscussionActivityBlock from '@/components/DiscussionActivityBlock.vue'
import translationPlugin from '../translation'
import { usersStore } from '@/stores/user'
import router from '../router'

export class DiscussionActivity {
	constructor({ data, api, readOnly }) {
		this.data = data
		this.readOnly = readOnly
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
		const discussionId = this.data.discussion || this.data.discussionID
		if (discussionId) {
			this.renderDiscussionActivity(discussionId)
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
			const app = createApp(DiscussionActivityBlock, {
				discussionID: discussion,
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
			onAddition: (discussion) => {
				this.data.discussion = discussion
				this.data.discussionID = discussion
				this.renderDiscussionActivity(discussion)
			},

		})
		app.use(translationPlugin)
		app.use(router) // Explicitly provide the router
		app.mount(this.wrapper)
	}

	save(blockContent) {
	const discussionId = this.data.discussion || this.data.discussionID
	if (!discussionId) {
		return {}
	}
	return {
		discussion: discussionId,
		discussionID: discussionId,
	}
	}
}
