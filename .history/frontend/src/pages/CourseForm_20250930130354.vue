<template>
	<div class="">
		<div class="grid md:grid-cols-[70%,30%] h-full">
			<div>
				<header
					class="sticky top-0 z-10 flex flex-col md:flex-row md:items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
				>
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
						<FormControl
							v-model="course.course"
							:label="__('Title')"
							class="mb-4"
							:required="true"
						/>
						<FormControl
							v-model="course.short_introduction"
							:label="__('Short Introduction')"
							:placeholder="
								__(
									'A one line introduction to the course that appears on the course card (less than 55 characters)'
								)
							"
							class="mb-2"
							:required="true"
						/>
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
							<TextEditor
								:content="course.course_description_for_lms"
								@change="(val) => (course.course_description_for_lms = val)"
								:editable="true"
								:fixedMenu="true"
								editorClass="prose-sm max-w-none border-b border-x bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[7rem]"
							/>
						</div>
						<div class="mb-4">
							<div class="text-xs text-ink-gray-5 mb-2">
								{{ __('Course Image') }}
								<span class="text-ink-red-3">*</span>
							</div>
							<FileUploader
								v-if="!course.course_image"
								:fileTypes="['image/*']"
								:validateFile="validateFile"
								@success="(file) => saveImage(file)"
							>
								<template
									v-slot="{ file, progress, uploading, openFileSelector }"
								>
									<div class="flex items-center">
										<div class="border rounded-md w-fit py-5 px-20">
											<Image class="size-5 stroke-1 text-ink-gray-7" />
										</div>
										<div class="ml-4">
											<Button @click="openFileSelector">
												{{ __('Upload') }}
											</Button>
											<div class="mt-2 text-ink-gray-5 text-sm">
												{{
													__('Appears on the course card in the course list')
												}}
											</div>
										</div>
									</div>
								</template>
							</FileUploader>
							<div v-else class="mb-4">
								<div class="flex items-center">
									<img
										:src="course.course_image.file_url"
										class="border rounded-md w-40"
									/>
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
							<MultiSelect
								v-model="instructorNames"
								doctype="Instructor"
								:label="__('Instructors')"
								:filters="{ Status: 'Active' }"
								:required="true"
							/>
						</div>
					</div>
					<div class="container border-t">
						<div v-if="user.data?.is_moderator"
							class="text-lg font-semibold mt-5 mb-4">
							{{ __('Settings') }}
						</div>
						<div class="grid grid-cols-2 gap-10 mb-4">
							<div
								v-if="user.data?.is_moderator"
								class="flex flex-col space-y-4"
							>
								<FormControl
									type="checkbox"
									v-model="course.published"
									:label="__('Published')"
								/>
							</div>
						</div>
					</div>
				</div>
			</div>
			<div class="border-l pt-5">
				<CourseOutline
					v-if="courseResource.data"
					:courseName="courseResource.data.name"
					:title="course.course"
					:allowEdit="true"
				/>
			</div>
		</div>
	</div>
</template>
<script setup>
import {
	Breadcrumbs,
	TextEditor,
	Button,
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
import { updateDocumentTitle } from '@/utils'
import Link from '@/components/Controls/Link.vue'
import { Image, Trash2, X } from 'lucide-vue-next'
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
const $dialog  = createDialog

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
})

const maxShortIntroductionLength = 55;

const remainingCharacters = computed(() => {
  const typedLength = course.short_introduction.length || 0;
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

const submitCourse = () => {
  if (courseResource.data) {
    fetch('/api/method/seminary.seminary.api.save_course', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Frappe-CSRF-Token': window.csrf_token,
      },
      body: JSON.stringify({
        course: courseResource.data.name,
        course_data: course,
      }),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        // Check success in the nested message object
        if (data.message && data.message.success) {
          toast.success(__('Course updated successfully'));
        } else {
          toast.error(err.messages?.[0] || err);
        }
      })
      .catch((error) => {
        console.error('Fetch error:', error);
        const errorMessage = typeof error === 'object' ? JSON.stringify(error) : error.toString();
        toast.error( errorMessage || __('An error occurred'));
      });
  }
};

const validateFile = (file) => {
	let extension = file.name.split('.').pop().toLowerCase()
	if (!['jpg', 'jpeg', 'png', 'webp'].includes(extension)) {
		return __('Only image file is allowed.')
	}
}

const saveImage = (file) => {
	course.course_image = file
}

const removeImage = () => {
	course.course_image = null
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
			label: 'Courses',
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
		label: 'Edit Course',
		route: { name: 'CourseForm', params: { courseName: props.courseName } },
	})
	return crumbs
})

const pageMeta = computed(() => {
	return {
		title: 'Edit Course',
		description: 'Edit a course for your learning system.',
	}
})

updateDocumentTitle(pageMeta)
</script>
