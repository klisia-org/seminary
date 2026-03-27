<template>
	<Dialog v-model="showProfileDialog" :options="dialogOptions" :disableOutsideClickToClose="true">
		<template #body-content>
			<!-- Student view (read-only) -->
			<div class="profile-dialog text-base max-h-[70vh] overflow-y-auto"
				v-if="isStudent && studentInfo.student_name">
				<div class="flex flex-col gap-4">
					<div class="flex items-center border-b border-solid border-lightGray pb-4 gap-2">
						<Avatar size="3xl" class="h-12 w-12" :label="studentInfo.student_name"
							:image="studentInfo.image || null" />
						<div class="flex flex-col ml-2 gap-1">
							<p class="text-lg font-semibold">{{ studentInfo.student_name }}</p>
							<p class="text-gray-600">{{ studentInfo.student_email_id }}</p>
						</div>
					</div>
					<div>
						<div class="flex gap-4">
							<div v-for="section in infoFormat" :key="section.section"
								class="flex-1 flex flex-col gap-4">
								<div v-for="field in section.fields" :key="field.label">
									<div class="flex items-center" v-if="field.label !== 'Address'">
										<p class="w-1/2 text-sm text-gray-600">{{ field.label }}:&nbsp;</p>
										<p class="w-1/2 text-gray-900">{{ field.value }}</p>
									</div>
								</div>
							</div>
						</div>
						<div class="flex items-center">
							<p class="w-[32%] text-sm text-gray-600"> {{ infoFormat[0].fields[3].label }}:&nbsp;</p>
							<p class="w-full text-gray-900">{{ infoFormat[0].fields[3].value }}</p>
						</div>
					</div>
					<div class="flex items-center bg-gray-50 p-2 text-gray-600 text-sm rounded-md">
						<FeatherIcon name="info" class="h-4 mr-2" />
						{{ __('In case of any incorrect details, please contact the school admin.') }}
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
import { Dialog, Avatar, FeatherIcon, createResource, Toast } from 'frappe-ui'
import { ref, computed, watchEffect, watch } from 'vue'
import { usersStore } from '../stores/user'
import Quill from 'quill'
import 'quill/dist/quill.snow.css'

let userResource = usersStore()

const showProfileDialog = defineModel({ default: false })

const studentInfo = ref({
	student_name: '',
	student_email_id: '',
	student_mobile_number: '',
	joining_date: '',
	date_of_birth: '',
	address_line_1: '',
	address_line_2: '',
	city: '',
	pincode: '',
	state: '',
	country: '',
	gender: '',
	nationality: ''
})

const studentResource = ref(null)
const instructorResource = ref(null)

const infoFormat = ref([])

watchEffect(() => {
	infoFormat.value = [
		{
			section: 'section 1',
			fields: [
				{
					label: __('Mobile Number'),
					value: studentInfo.value.student_mobile_number,
				},
				{
					label: __('Joining Date'),
					value: studentInfo.value.joining_date,
				},
				{
					label: __('Date of Birth'),
					value: studentInfo.value.date_of_birth,
				},
				{
					label: __('Address'),
					value: [
						studentInfo.value.address_line_1,
						studentInfo.value.address_line_2,
						studentInfo.value.city,
						studentInfo.value.pincode,
						studentInfo.value.state,
						studentInfo.value.country
					].map(item => item?.trim()).filter(Boolean).join(', ')
				},
			]
		},
		{
			section: 'section 2',
			fields: [
				{
					label: __('Gender'),
					value: studentInfo.value.gender
				},
				{
					label: __('Nationality'),
					value: studentInfo.value.nationality
				},
			]
		},
	]
})

const instructorInfo = ref({
	instructor_name: '',
	user: '',
	bio: '',
	shortbio: '',
	profileimage: '',
})

const editName = ref('')
const editShortbio = ref('')
const bioEditorDiv = ref(null)
let bioQuill = null

const isStudent = ref(false)
const user = ref('')

watchEffect(() => {
	if (userResource.userResource.data) {
		isStudent.value = userResource.userResource.data.is_student
		user.value = userResource.userResource.data.name

		if (isStudent.value && !studentResource.value) {
			studentResource.value = createResource({
				url: 'seminary.seminary.api.get_student_info',
				params: { student: user.value },
				onSuccess: (response) => {
					Object.assign(studentInfo.value, response)
				},
				auto: true,
			})
		}

		if (!isStudent.value && !instructorResource.value) {
			instructorResource.value = createResource({
				url: 'seminary.seminary.api.get_instructor_info',
				params: { instructor: user.value },
				onSuccess: (response) => {
					Object.assign(instructorInfo.value, response)
					editName.value = response.instructor_name || ''
					editShortbio.value = response.shortbio || ''
					if (bioQuill) bioQuill.root.innerHTML = response.bio || ''
				},
				auto: true,
			})
		}
	}
})

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

const saveResource = createResource({
	url: 'seminary.seminary.api.save_instructor_profile',
	onSuccess(data) {
		Object.assign(instructorInfo.value, data)
		toast.success(__('Profile saved'))
	},
	onError(err) {
		toast.error(err.messages?.[0] || err)
	},
})

const saveInstructor = () => {
	saveResource.submit({
		instructor_name: editName.value,
		shortbio: editShortbio.value,
		bio: bioQuill?.root.innerHTML || '',
	})
}

const handleClose = (close) => {
	showProfileDialog.value = false
	close?.()
}

const dialogOptions = computed(() => ({
	title: __('Profile'),
	size: 'xl',
	actions: [
		...(!isStudent.value ? [{
			label: __('Save'),
			variant: 'solid',
			onClick: saveInstructor,
		}] : []),
		{
			label: __('Close'),
			variant: 'text',
			onClick: (close) => handleClose(close),
		},
	],
}))
</script>
