<template>
	<div class="">
		<div class="grid md:grid-cols-[70%,30%] h-full">
			<div>
				<header
					class="sticky top-0 z-10 flex flex-col md:flex-row md:items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
					<Breadcrumbs class="h-7" :items="breadcrumbs" />
					<div class="flex items-center mt-3 md:mt-0">
						<Button variant="solid" @click="submitCourse()" class="ml-2">
							<span>
								{{ __('Save') }}
							</span>
						</Button>
					</div>
				</header>
				<div class="mt-5 mb-10">
					<div class="container mb-5">
						<div class="text-lg font-semibold mb-4">
							{{ __('Details') }}
						</div>
						<FormControl v-model="course.course" :label="__('Title')" class="mb-4" :required="true" />
						<FormControl v-model="course.short_introduction" :label="__('Short Introduction')" :placeholder="__(
							'A one line introduction to the course that appears on the course card (less than 55 characters)'
						)
							" class="mb-2" :required="true" />
						<div class="text-sm mt-1" :class="remainingCharacters < 0 ? 'text-red-500' : 'text-ink-gray-5'">
							<span v-if="remainingCharacters >= 0">
								{{ `${remainingCharacters} characters available` }}
							</span>
							<span v-else>
								{{ __('This introduction may be truncated on the course card.') }}
							</span>
						</div>
						<div class="mb-4">
							<div class="mb-1.5 mt-4 text-sm text-ink-gray-5">
								{{ __('Course Description') }}
								<span class="text-ink-red-3">*</span>
							</div>
							<TextEditor :content="course.course_description_for_lms"
								@change="(val) => (course.course_description_for_lms = val)" :editable="true"
								:fixedMenu="true"
								editorClass="prose-sm max-w-none border-b border-x bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[7rem]" />
						</div>
						<div class="mb-4">
							<div class="text-xs text-ink-gray-5 mb-2">
								{{ __('Course Image') }}
								<span class="text-ink-red-3">*</span>
							</div>
							<FileUploader v-if="!course.course_image" :fileTypes="['image/*']"
								:validateFile="validateFile" @success="(file) => saveImage(file)">
								<template v-slot="{ file, progress, uploading, openFileSelector }">
									<div class="flex items-center">
										<div class="border rounded-md w-fit py-5 px-20">
											<Image class="size-5 stroke-1 text-ink-gray-7" />
										</div>
										<div class="ml-4">
											<div class="flex items-center gap-2">
												<Button @click="openFileSelector">
													{{ __('Upload') }}
												</Button>
												<Button @click="openPexelsDialog()">
													{{ __('Choose from Pexels') }}
												</Button>
											</div>
											<div class="mt-2 text-ink-gray-5 text-sm">
												{{
													__('Appears on the course card in the course list')
												}}
												<span v-if="uploadLimits.data?.max_upload_mb">
													·
													{{ __('Max {0} MB').format(uploadLimits.data.max_upload_mb) }}
												</span>
											</div>
										</div>
									</div>
								</template>
							</FileUploader>
							<div v-else class="mb-4">
								<div class="flex items-center">
									<img :src="course.course_image.file_url" class="border rounded-md w-40" />
									<div class="ml-4">
										<Button @click="removeImage()">
											{{ __('Remove') }}
										</Button>
										<div class="mt-2 text-ink-gray-5 text-sm">
											{{ __('Appears on the course card in the course list') }}
										</div>
									</div>
								</div>
							</div>
						</div>

						<div class="mb-4">
							<MultiSelect v-model="instructorNames" doctype="Instructor" :label="__('Instructors')"
								:filters="{ Status: 'Active' }" :required="true" />
						</div>

						<FormControl v-model="course.web_meeting" type="url" :label="__('Web Meeting Link')"
							:placeholder="__('https://zoom.us/j/...')" class="mb-4" />
						<div class="text-sm text-ink-gray-5 -mt-2 mb-4">
							{{ __('Link students use to join the online class session (Zoom, Meet, Teams, etc.).') }}
						</div>

						<!-- Online meetings: instructor self-service, no registrar (ADR 051) -->
						<div class="mb-4">
							<div class="flex items-center justify-between mb-1">
								<div class="text-sm font-medium text-ink-gray-7">{{ __('Online Meetings') }}</div>
								<Button size="sm" @click="openVirtualDialog()">
									<template #prefix><Video class="h-4 w-4" /></template>
									{{ __('Schedule a virtual meeting') }}
								</Button>
							</div>
							<div class="text-sm text-ink-gray-5 mb-2">
								{{ __('Add an online class session to the course calendar — no room or registrar needed. It syncs to subscribers’ calendars.') }}
							</div>
							<div v-if="virtualMeetings.data?.length" class="border rounded-md divide-y">
								<div v-for="m in virtualMeetings.data" :key="m.name"
									class="flex items-center justify-between px-3 py-2 text-sm gap-3">
									<div class="min-w-0">
										<span class="font-medium text-ink-gray-8">{{ m.cs_meetdate }}</span>
										<span v-if="m.cs_fromtime" class="text-ink-gray-5">
											· {{ hhmm(m.cs_fromtime) }}–{{ hhmm(m.cs_totime) }}
										</span>
									</div>
									<div class="flex items-center gap-2 shrink-0">
										<a v-if="m.cs_web_meeting || course.web_meeting"
											:href="m.cs_web_meeting || course.web_meeting" target="_blank"
											rel="noopener noreferrer" class="no-underline">
											<Button size="sm" variant="subtle">
												<template #prefix><Video class="h-4 w-4" /></template>
												{{ __('Join') }}
											</Button>
										</a>
										<span v-if="m.attendance" class="text-xs text-ink-gray-4">
											{{ __('Attendance recorded') }}
										</span>
										<Button v-else size="sm" variant="ghost" theme="red"
											@click="removeVirtualMeeting(m.name)">
											<template #icon><Trash2 class="h-4 w-4" /></template>
										</Button>
									</div>
								</div>
							</div>
							<div v-else class="text-xs text-ink-gray-4">
								{{ __('No online meetings scheduled yet.') }}
							</div>
						</div>
					</div>
					<div class="container border-t">
						<div v-if="user.data?.is_moderator" class="text-lg font-semibold mt-5 mb-4">
							{{ __('Settings') }}
						</div>
						<div class="grid grid-cols-2 gap-10 mb-4">
							<div v-if="user.data?.is_moderator" class="flex flex-col space-y-4">
								<FormControl type="checkbox" v-model="course.published" :label="__('Published')" />
							</div>
						</div>
					</div>
				</div>
			</div>
			<div class="border-l pt-5">
				<CourseOutline v-if="courseResource.data" :courseName="courseResource.data.name" :title="course.course"
					:allowEdit="true" />
			</div>
		</div>

		<!-- Schedule a virtual meeting (online only: date, from, to, link) -->
		<Dialog v-model="showVirtualDialog" :options="{ title: __('Schedule a virtual meeting') }">
			<template #body-content>
				<div class="space-y-3">
					<p class="text-sm text-ink-gray-6">
						{{ __('Adds an online session to the course calendar. No room or registrar needed.') }}
					</p>
					<FormControl type="date" v-model="vForm.meeting_date" :label="__('Date')" :required="true" />
					<div class="grid grid-cols-2 gap-3">
						<FormControl type="time" v-model="vForm.from_time" :label="__('From')" :required="true" />
						<FormControl type="time" v-model="vForm.to_time" :label="__('To')" :required="true" />
					</div>
					<FormControl type="url" v-model="vForm.link" :label="__('Meeting Link')"
						:placeholder="__('https://zoom.us/j/...')"
						:description="__('Leave blank to use the course Web Meeting Link above.')" />
				</div>
			</template>
			<template #actions>
				<Button @click="showVirtualDialog = false">{{ __('Cancel') }}</Button>
				<Button variant="solid" :loading="savingVirtual" @click="addVirtualMeeting()">
					{{ __('Add to calendar') }}
				</Button>
			</template>
		</Dialog>

		<!-- Pick a free course image from Pexels (no attribution required) -->
		<Dialog v-model="showPexelsDialog" :options="{ title: __('Choose an image from Pexels'), size: '3xl' }">
			<template #body-content>
				<div class="space-y-4">
					<form class="flex items-center gap-2" @submit.prevent="searchPexels()">
						<FormControl class="flex-1" type="text" v-model="pexelsQuery"
							:placeholder="__('Search free photos (e.g. theology, church, books)')" />
						<Button variant="solid" :loading="pexelsLoading" @click="searchPexels()">
							{{ __('Search') }}
						</Button>
					</form>
					<p class="text-xs text-ink-gray-5">
						{{ __('Photos provided by Pexels. No attribution required.') }}
					</p>

					<div v-if="pexelsError" class="text-sm text-ink-red-3">
						{{ pexelsError }}
					</div>

					<div v-if="pexelsResults.length"
						class="grid grid-cols-2 sm:grid-cols-3 gap-3 max-h-[55vh] overflow-y-auto">
						<button v-for="photo in pexelsResults" :key="photo.id" type="button"
							class="relative rounded-md overflow-hidden border hover:ring-2 hover:ring-outline-gray-3 focus:outline-none focus:ring-2 focus:ring-outline-gray-4 aspect-[4/3]"
							:disabled="downloadingId !== null" @click="selectPexelsPhoto(photo)">
							<img :src="photo.thumb" :alt="photo.alt" loading="lazy"
								class="w-full h-full object-cover" />
							<div v-if="downloadingId === photo.id"
								class="absolute inset-0 flex items-center justify-center bg-black/40 text-white text-sm">
								{{ __('Adding…') }}
							</div>
						</button>
					</div>

					<div v-else-if="pexelsSearched && !pexelsLoading" class="text-sm text-ink-gray-5 py-6 text-center">
						{{ __('No photos found. Try a different search.') }}
					</div>

					<div v-if="pexelsNextPage" class="flex justify-center">
						<Button :loading="pexelsLoadingMore" @click="loadMorePexels()">
							{{ __('Load more') }}
						</Button>
					</div>
				</div>
			</template>
		</Dialog>
	</div>
</template>
<script setup>
import {
	Breadcrumbs,
	TextEditor,
	Button,
	Dialog,
	call,
	createResource,
	FormControl,
	FileUploader,
	toast,
} from 'frappe-ui'
import {
	inject,
	onMounted,
	onBeforeUnmount,
	computed,
	ref,
	reactive,
	watch,
	getCurrentInstance,
} from 'vue'
import { updateDocumentTitle, uploadLimits, validateFileSize } from '@/utils'
import Link from '@/components/Controls/Link.vue'
import { Image, Trash2, Video, X } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import CourseOutline from '@/components/CourseOutline.vue'
import MultiSelect from '@/components/Controls/MultiSelect.vue'
import { capture } from '@/telemetry'
import { useSettings } from '@/stores/settings'
import { createDialog } from '@/utils/dialogs.js'

const user = inject('$user')
const newTag = ref('')
const router = useRouter()
const instructors = ref([])
const instructorNames = ref([])
const settingsStore = useSettings()
const app = getCurrentInstance()
const $dialog = createDialog

const props = defineProps({
	courseName: {
		type: String,
	},
})

const course = reactive({
	course: '',
	short_introduction: '',
	course_description_for_lms: '',
	course_image: null,
	published: false,
	web_meeting: '',
})

// --- Online (virtual) meetings: instructor self-service (ADR 051) ----------
const showVirtualDialog = ref(false)
const savingVirtual = ref(false)
const vForm = reactive({ meeting_date: '', from_time: '', to_time: '', link: '' })

const hhmm = (t) => (t ? String(t).split(':').slice(0, 2).join(':') : '')

const virtualMeetings = createResource({
	url: 'seminary.seminary.api.get_virtual_meetings',
	makeParams() {
		return { course_schedule: props.courseName }
	},
	auto: false,
})

const openVirtualDialog = () => {
	vForm.meeting_date = ''
	vForm.from_time = ''
	vForm.to_time = ''
	vForm.link = ''
	showVirtualDialog.value = true
}

const addVirtualMeeting = async () => {
	if (!vForm.meeting_date || !vForm.from_time || !vForm.to_time) {
		toast.error(__('Date, From and To times are required.'))
		return
	}
	savingVirtual.value = true
	try {
		await call('seminary.seminary.api.add_virtual_meeting', {
			course_schedule: props.courseName,
			meeting_date: vForm.meeting_date,
			from_time: vForm.from_time,
			to_time: vForm.to_time,
			link: vForm.link || null,
		})
		toast.success(__('Virtual meeting added to the calendar'))
		showVirtualDialog.value = false
		virtualMeetings.reload()
	} catch (e) {
		toast.error(e?.messages?.[0] || e?.message || __('Could not add the meeting'))
	} finally {
		savingVirtual.value = false
	}
}

const removeVirtualMeeting = async (name) => {
	try {
		await call('seminary.seminary.api.remove_virtual_meeting', {
			course_schedule: props.courseName,
			meeting: name,
		})
		toast.success(__('Online meeting removed'))
		virtualMeetings.reload()
	} catch (e) {
		toast.error(e?.messages?.[0] || e?.message || __('Could not remove the meeting'))
	}
}

const maxShortIntroductionLength = 55;

const remainingCharacters = computed(() => {
	const typedLength = course.short_introduction?.length || 0;
	return maxShortIntroductionLength - typedLength;
});

onMounted(() => {
	courseResource.reload()
	window.addEventListener('keydown', keyboardShortcut)
})

const keyboardShortcut = (e) => {
	if (
		e.key === 's' &&
		(e.ctrlKey || e.metaKey) &&
		!e.target.classList.contains('ProseMirror')
	) {
		submitCourse()
		e.preventDefault()
	}
}

onBeforeUnmount(() => {
	window.removeEventListener('keydown', keyboardShortcut)
})



// const instructorEditResource = createResource({
// 	url: 'frappe.client.set_value',
// 	auto: false,
// 	makeParams(values) {
// 		return {
// 			doctype: 'Course Schedule Instructors',
// 			parent: values.course,
// 			fieldname: {
// 				instructor1: instructors.value.map((instructor, index) => ({
// 					instructor: instructor.instructor,
// 					idx: index + 1,
// 					parent: values.course,
// 					parentfield: 'instructor1',
// 					parenttype: 'Course Schedule',
// 					user: instructor.user,
// 				})),
// 			},
// 		}
// 	},
// })

const courseResource = createResource({
	url: 'frappe.client.get',
	makeParams(values) {
		return {
			doctype: 'Course Schedule',
			name: props.courseName,
		}
	},
	auto: false,
	onSuccess(data) {

		if (!data) {
			console.error('No data received from courseResource')
			return
		}
		Object.keys(data).forEach((key) => {
			if (key == 'instructor1') {
				instructors.value = []
				instructorNames.value = []
				data.instructor1.forEach((instructor) => {
					instructors.value.push(instructor)
					instructorNames.value.push(instructor.instructor)
				})
			} else if (Object.hasOwn(course, key)) course[key] = data[key]
		})
		let checkboxes = ['published']
		for (let idx in checkboxes) {
			let key = checkboxes[idx]
			course[key] = course[key] ? true : false
		}

		if (data.course_image) imageResource.reload({ image: data.course_image })
		virtualMeetings.reload()
		check_permission()
	},
	onError(err) {
		console.error('courseResource onError:', err)
	}
})

const imageResource = createResource({
	url: 'seminary.seminary.api.get_file_info',
	makeParams(values) {
		return {
			file_url: values.image,
		}
	},
	auto: false,
	onSuccess(data) {

		course.course_image = data
	},
	onError(err) {
		console.error('imageResource onError:', err)
	}
})

const getCsrfToken = () =>
	window.csrf_token ||
	window.frappe?.csrf_token ||
	document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
	''

const submitCourse = async () => {
	if (!courseResource.data) return;
	try {
		const response = await fetch('/api/method/seminary.seminary.api.save_course', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				'X-Frappe-CSRF-Token': getCsrfToken(),
			},
			body: JSON.stringify({
				course: courseResource.data.name,
				course_data: course,
			}),
		});
		const payload = await response.json().catch(() => ({}));
		if (!response.ok) {
			const message = payload?._server_messages
				? JSON.parse(payload._server_messages)
						.map((m) => {
							try { return JSON.parse(m).message; } catch { return m; }
						})
						.join('\n')
				: payload?.exception || payload?.message || `HTTP ${response.status}`;
			throw new Error(message);
		}
		if (payload.message && payload.message.success) {
			toast.success(__('Course updated successfully'));
		} else {
			toast.error(payload?.message?.error || __('An error occurred'));
		}
	} catch (error) {
		console.error('Fetch error:', error);
		toast.error(error?.message || __('An error occurred'));
	}
};

const validateFile = (file) => {
	let extension = file.name.split('.').pop().toLowerCase()
	if (!['jpg', 'jpeg', 'png', 'webp'].includes(extension)) {
		return __('Only image file is allowed.')
	}
	return validateFileSize(file)
}

const saveImage = (file) => {
	course.course_image = file
}

const removeImage = () => {
	course.course_image = null
}

// --- Pexels stock-photo picker ---------------------------------------------
const showPexelsDialog = ref(false)
const pexelsQuery = ref('')
const pexelsResults = ref([])
const pexelsPage = ref(1)
const pexelsNextPage = ref(null)
const pexelsLoading = ref(false)
const pexelsLoadingMore = ref(false)
const pexelsSearched = ref(false)
const pexelsError = ref('')
const downloadingId = ref(null)

const openPexelsDialog = () => {
	pexelsError.value = ''
	showPexelsDialog.value = true
}

const runPexelsSearch = async (page) => {
	pexelsError.value = ''
	try {
		const res = await call('seminary.seminary.integrations.pexels.search_photos', {
			query: pexelsQuery.value,
			page,
		})
		if (page === 1) {
			pexelsResults.value = res.photos
		} else {
			pexelsResults.value = pexelsResults.value.concat(res.photos)
		}
		pexelsPage.value = page
		pexelsNextPage.value = res.next_page
	} catch (error) {
		pexelsError.value =
			error?.messages?.join('\n') || error?.message || __('Could not search Pexels.')
	}
}

const searchPexels = async () => {
	if (!pexelsQuery.value.trim()) return
	pexelsLoading.value = true
	pexelsSearched.value = true
	pexelsResults.value = []
	pexelsNextPage.value = null
	await runPexelsSearch(1)
	pexelsLoading.value = false
}

const loadMorePexels = async () => {
	if (!pexelsNextPage.value) return
	pexelsLoadingMore.value = true
	await runPexelsSearch(pexelsNextPage.value)
	pexelsLoadingMore.value = false
}

const selectPexelsPhoto = async (photo) => {
	if (downloadingId.value !== null) return
	downloadingId.value = photo.id
	try {
		const file = await call('seminary.seminary.integrations.pexels.download_photo', {
			src_url: photo.full,
		})
		saveImage(file)
		showPexelsDialog.value = false
	} catch (error) {
		toast.error(
			error?.messages?.join('\n') || error?.message || __('Could not add this image.')
		)
	} finally {
		downloadingId.value = null
	}
}

const check_permission = () => {
	let user_is_instructor = false
	if (user.data?.is_moderator) return

	instructors.value.forEach((instructor) => {
		if (!user_is_instructor && instructor.user == user.data?.name) {
			user_is_instructor = true
		}
	})


	if (!user_is_instructor) {
		console.log('Redirecting to Courses due to insufficient permissions')
		router.push({ name: 'Courses' })
	}
}

const breadcrumbs = computed(() => {
	let crumbs = [
		{
			label: __('Courses'),
			route: { name: 'Courses' },
		},
	]
	if (courseResource.data) {
		crumbs.push({
			label: course.course,
			route: { name: 'CourseDetail', params: { courseName: props.courseName } },
		})
	}
	crumbs.push({
		label: __('Edit Course'),
		route: { name: 'CourseForm', params: { courseName: props.courseName } },
	})
	return crumbs
})

const pageMeta = computed(() => {
	return {
		title: __('Edit Course'),
		description: __('Edit a course for your learning system.'),
	}
})

updateDocumentTitle(pageMeta)
</script>
