import { MessagesSquare } from 'lucide-vue-next'
import { createApp, h } from 'vue'
import AssessmentPlugin from '@/components/AssessmentPlugin.vue'
import DiscussionActivityBlock from '@/components/DiscussionActivityBlock.vue'
import translationPlugin from '../translation'
import { usersStore } from '@/stores/user'
import router from '../router'
import { FrappeUI, setConfig, frappeRequest, pageMetaPlugin } from 'frappe-ui'

export class DiscussionActivity {
	constructor({ data, api, readOnly, config }) {
		this.data = data
		this.readOnly = readOnly
		this.course = config?.course || null
		this.courseName = config?.courseName || null
		this._app = null
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
			const app = createApp(DiscussionActivityBlock, {
				discussionID: discussion,
				courseName: this.courseName,
			})
			app.use(translationPlugin)
			app.use(FrappeUI)
			app.use(router)
			const { userResource } = usersStore()
			app.provide('$user', userResource)
			app.mount(this.wrapper)
			this._app = app
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
		app.use(FrappeUI)
		app.use(router) // Explicitly provide the router
		app.mount(this.wrapper)
	}

	destroy() {
		if (this._app) {
			this._app.unmount()
			this._app = null
		}
	}

	save(blockContent) {
		return {
			discussion: this.data.discussion,
		}
	}
}
