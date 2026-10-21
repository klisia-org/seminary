<template>
	<!-- A partner school's own questions (aretenic; privatedocs p012 decision 4).
	     Kept apart from the goals: these are answers in prose that the partner
	     receives, not growth the student plans. -->
	<div v-if="reviews.data?.length">
		<section v-for="form in reviews.data" :key="form.form"
			class="mt-6 rounded-md border border-outline-gray-2 px-4 py-4">
			<h2 class="font-semibold text-ink-gray-8">{{ form.title }}</h2>
			<p class="mt-1 text-sm text-ink-gray-6">
				{{ form.status === 'Submitted'
					? __('Submitted. {0} receives these answers with your review.').format(form.partner)
					: __('{0} asks these questions at the end of each course. Your answers go to them with your review.').format(form.partner) }}
			</p>
			<div v-for="q in form.questions" :key="q.name" class="mt-4">
				<SafeHtml class="prose-sm text-ink-gray-8" :html="q.question" />
				<FormControl class="mt-2" type="textarea" :rows="4" :disabled="!form.editable"
					v-model="drafts[form.form][q.name]" />
			</div>
			<div v-if="form.editable" class="mt-4 flex flex-wrap items-center gap-2">
				<Button variant="subtle" :loading="saving === form.form + ':draft'" @click="save(form, false)">
					{{ __('Save Answers') }}
				</Button>
				<Button variant="solid" :loading="saving === form.form + ':submit'" @click="save(form, true)">
					{{ __('Submit Answers') }}
				</Button>
				<span class="text-sm text-ink-gray-6">
					{{ __('Submitting is final.') }}
				</span>
			</div>
		</section>
	</div>
</template>

<script setup>
import { Button, FormControl, call, createResource, toast } from 'frappe-ui'
import { reactive, ref } from 'vue'

const props = defineProps({
	courseName: { type: String, required: true },
	student: { type: String, default: null },
})
const drafts = reactive({})
const saving = ref(null)

const reviews = createResource({
	url: 'aretenic.partner_reviews.get_partner_reviews',
	makeParams: () => ({
		course_schedule: props.courseName,
		student: props.student || undefined,
	}),
	auto: true,
	onSuccess(data) {
		for (const form of data || []) {
			drafts[form.form] = Object.fromEntries(form.questions.map((q) => [q.name, q.answer || '']))
		}
	},
})

async function save(form, submit) {
	saving.value = form.form + (submit ? ':submit' : ':draft')
	try {
		await call('aretenic.partner_reviews.save_partner_answers', {
			course_schedule: props.courseName,
			form: form.form,
			answers: JSON.stringify(drafts[form.form] || {}),
			submit: submit ? 1 : 0,
		})
		toast.success(submit ? __('Answers submitted') : __('Answers saved'))
		reviews.reload()
	} catch (e) {
		toast.error(e?.messages?.[0] || e?.message || __('Could not save your answers'))
	} finally {
		saving.value = null
	}
}
</script>
