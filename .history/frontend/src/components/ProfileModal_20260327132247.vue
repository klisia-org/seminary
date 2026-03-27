<template>
	<Dialog v-model="showProfileDialog" :options="dialogOptions" :disableOutsideClickToClose="true">
		<template #body-content>

			<!-- Student view (editable) -->
			<div class="profile-dialog text-base max-h-[70vh] overflow-y-auto"
				v-if="isStudent && studentInfo.student_name">
				<div class="flex flex-col gap-4">

					<!-- Header with editable avatar -->
					<div class="flex items-center border-b border-solid border-lightGray pb-4 gap-2">
						<div class="relative group flex-shrink-0">
							<Avatar size="3xl" class="h-12 w-12" :label="studentInfo.student_name"
								:image="editImage || studentInfo.image || null" />
							<FileUploader :fileTypes="['image/*']" @success="(f) => { editImage = f.file_url }">
								<template #default="{ uploading, openFileSelector }">
									<button @click="openFileSelector"
										class="absolute inset-0 flex items-center justify-center bg-black/40 rounded-full opacity-0 group-hover:opacity-100 transition-opacity">
										<FeatherIcon v-if="!uploading" name="camera" class="h-4 w-4 text-white" />
										<FeatherIcon v-else name="loader" class="h-4 w-4 text-white animate-spin" />
									</button>
								</template>
							</FileUploader>
						</div>
						<div class="flex flex-col ml-2 gap-1">
							<p class="text-lg font-semibold">{{ studentInfo.student_name }}</p>
							<p class="text-gray-600">{{ studentInfo.student_email_id }}</p>
						</div>
					</div>

					<!-- Success message -->
					<div v-if="saveSuccess"
						class="flex items-center gap-2 rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">
						<FeatherIcon name="check-circle" class="h-4 w-4 flex-shrink-0" />
						{{ __('Profile saved successfully.') }}
					</div>

					<!-- Editable: Mobile -->
					<div>
						<label class="text-sm text-gray-600">{{ __('Mobile Number') }}</label>
						<input v-model="editMobile" type="text"
							class="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500" />
					</div>

					<!-- Editable: Address -->
					<div class="flex flex-col gap-2">
						<label class="text-sm text-gray-600">{{ __('Address') }}</label>
						<input v-model="editAddr.address_line_1" type="text" :placeholder="__('Address Line 1')"
							class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500" />
						<input v-model="editAddr.address_line_2" type="text" :placeholder="__('Address Line 2')"
							class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500" />
						<div class="grid grid-cols-3 gap-2">
							<input v-model="editAddr.city" type="text" :placeholder="__('City')"
								class="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500" />
							<input v-model="editAddr.state" type="text" :placeholder="__('State')"
								class="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500" />
							<input v-model="editAddr.pincode" type="text" :placeholder="__('Pincode')"
								class="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500" />
						</div>
						<input v-model="editAddr.country" type="text" :placeholder="__('Country')"
							class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500" />
					</div>

					<!-- Read-only fields -->
					<div class="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
						<div v-for="field in readOnlyFields" :key="field.label" class="flex">
							<span class="text-gray-500 w-32 flex-shrink-0">{{ field.label }}:</span>
							<span class="text-gray-900">{{ field.value }}</span>
						</div>
					</div>

					<!-- Note with support mailto -->
					<div class="flex items-start bg-gray-50 p-2 text-gray-600 text-sm rounded-md">
						<FeatherIcon name="info" class="h-4 w-4 mr-2 flex-shrink-0 mt-0.5" />
						<span>
							{{ __('In case of any incorrect details, please contact') }}
							<a v-if="supportUser" :href="`mailto:${supportUser}`" class="text-blue-600 underline ml-1">
								{{ __(' the school admin') }}</a>
							<span v-else>{{ __(' the school admin') }}</span>.
						</span>
					</div>
				</div>
			</div>

			<!-- Instructor view (editable) -->
			<div class="profile-dialog text-base max-h-[70vh] overflow-y-auto" v-else-if="!isStudent">
				<div class="flex flex-col gap-4">
					<div class="flex items-center border-b border-solid border-lightGray pb-4 gap-2">
						<Avatar size="3xl" class="h-12 w-12" :label="instructorInfo.instructor_name"
							:image="instructorInfo.profileimage || null" />
						<div class="flex flex-col ml-2 gap-1">
							<p class="text-lg font-semibold">{{ instructorInfo.instructor_name }}</p>
							<p class="text-gray-600">{{ instructorInfo.user }}</p>
						</div>
					</div>
					<div v-if="saveSuccess"
						class="flex items-center gap-2 rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">
						<FeatherIcon name="check-circle" class="h-4 w-4 flex-shrink-0" />
						{{ __('Profile saved successfully.') }}
					</div>
					<div class="flex flex-col gap-3">
						<div>
							<label class="text-sm text-gray-600">{{ __('Name') }}</label>
							<input v-model="editName" type="text"
								class="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500" />
						</div>
						<div>
							<label class="text-sm text-gray-600">{{ __('Short Bio') }}</label>
							<input v-model="editShortbio" type="text"
								class="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500" />
						</div>
						<div>
							<label class="text-sm text-gray-600 mb-1 block">{{ __('Bio') }}</label>
							<div ref="bioEditorDiv"></div>
						</div>
					</div>
				</div>
			</div>

		</template>
	</Dialog>
</template>

<script setup>
import { Dialog, Avatar, FeatherIcon, FileUploader, createResource } from 'frappe-ui'
import { ref, computed, watchEffect, watch } from 'vue'
import { usersStore } from '../stores/user'
import Quill from 'quill'
import 'quill/dist/quill.snow.css'

const { userResource } = usersStore()

const showProfileDialog = defineModel({ default: false })

// ── Shared ────────────────────────────────────────────────────────────────────
const isStudent = ref(false)
const user = ref('')
const saveSuccess = ref(false)

const handleClose = (close) => {
	showProfileDialog.value = false
	saveSuccess.value = false
	close?.()
}

// ── Seminary settings (support_user) ─────────────────────────────────────────
const supportUser = ref('')
createResource({
	url: 'seminary.seminary.api.get_school_abbr_logo',
	auto: true,
	onSuccess(data) {
		supportUser.value = data.support_user || ''
	},
})


// ── Student ───────────────────────────────────────────────────────────────────
const studentInfo = ref({
	student_name: '', student_email_id: '', student_mobile_number: '',
	joining_date: '', date_of_birth: '', gender: '', nationality: '',
	address_line_1: '', address_line_2: '', city: '', pincode: '', state: '', country: '',
	image: '',
})

const editImage = ref('')
const editMobile = ref('')
const editAddr = ref({
	address_line_1: '', address_line_2: '', city: '', pincode: '', state: '', country: '',
})

const readOnlyFields = computed(() => [
	{ label: __('Joining Date'), value: studentInfo.value.joining_date },
	{ label: __('Date of Birth'), value: studentInfo.value.date_of_birth },
	{ label: __('Gender'), value: studentInfo.value.gender },
	{ label: __('Nationality'), value: studentInfo.value.nationality },
])

const saveStudentResource = createResource({
	url: 'seminary.seminary.api.save_student_profile',
	onSuccess(data) {
		Object.assign(studentInfo.value, data)
		saveSuccess.value = true
		setTimeout(() => handleClose(), 1000)
	},
	onError(err) {
		console.error(err.messages?.[0] || err)
	},
})

const saveStudent = () => {
	saveStudentResource.submit({
		mobile: editMobile.value,
		address_line_1: editAddr.value.address_line_1,
		address_line_2: editAddr.value.address_line_2,
		city: editAddr.value.city,
		pincode: editAddr.value.pincode,
		state: editAddr.value.state,
		country: editAddr.value.country,
		image: editImage.value || null,
	})
}

// ── Instructor ────────────────────────────────────────────────────────────────
const instructorInfo = ref({
	instructor_name: '', user: '', bio: '', shortbio: '', profileimage: '',
})

const editName = ref('')
const editShortbio = ref('')
const bioEditorDiv = ref(null)
let bioQuill = null

watch(bioEditorDiv, (el) => {
	if (el) {
		bioQuill = new Quill(el, {
			theme: 'snow',
			modules: {
				toolbar: [['bold', 'italic'], [{ list: 'ordered' }, { list: 'bullet' }], ['link']],
			},
		})
		bioQuill.root.innerHTML = instructorInfo.value.bio || ''
	} else {
		bioQuill = null
	}
})

const saveInstructorResource = createResource({
	url: 'seminary.seminary.api.save_instructor_profile',
	onSuccess(data) {
		Object.assign(instructorInfo.value, data)
		saveSuccess.value = true
		setTimeout(() => handleClose(), 1000)
	},
	onError(err) {
		console.error(err.messages?.[0] || err)
	},
})

const saveInstructor = () => {
	saveInstructorResource.submit({
		instructor_name: editName.value,
		shortbio: editShortbio.value,
		bio: bioQuill?.root.innerHTML || '',
	})
}

// ── Bootstrap resources when user data is available ──────────────────────────
const studentResource = ref(null)
const instructorResource = ref(null)

watchEffect(() => {
	if (!userResource.data) return
	isStudent.value = userResource.data.is_student
	user.value = userResource.data.name

	if (isStudent.value && !studentResource.value) {
		studentResource.value = createResource({
			url: 'seminary.seminary.api.get_student_info',
			auto: true,
			onSuccess(response) {
				Object.assign(studentInfo.value, response)
				editMobile.value = response.student_mobile_number || ''
				editAddr.value = {
					address_line_1: response.address_line_1 || '',
					address_line_2: response.address_line_2 || '',
					city: response.city || '',
					pincode: response.pincode || '',
					state: response.state || '',
					country: response.country || '',
				}
				editImage.value = response.image || ''
			},
		})
	}

	if (!isStudent.value && !instructorResource.value) {
		instructorResource.value = createResource({
			url: 'seminary.seminary.api.get_instructor_info',
			auto: true,
			onSuccess(response) {
				Object.assign(instructorInfo.value, response)
				editName.value = response.instructor_name || ''
				editShortbio.value = response.shortbio || ''
				if (bioQuill) bioQuill.root.innerHTML = response.bio || ''
			},
		})
	}
})

// ── Dialog options ────────────────────────────────────────────────────────────
const dialogOptions = computed(() => ({
	title: __('Profile'),
	size: 'xl',
	actions: [
		{
			label: __('Save'),
			variant: 'solid',
			onClick: isStudent.value ? saveStudent : saveInstructor,
		},
		{
			label: __('Close'),
			variant: 'text',
			onClick: (close) => handleClose(close),
		},
	],
}))
</script>
