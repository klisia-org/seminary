<template>
	<Dialog v-model="showProfileDialog" :options="dialogOptions" :disableOutsideClickToClose="true">
		<template #body-content>

			<!-- Student view (editable) -->
			<div class="profile-dialog text-base text-ink-gray-9 max-h-[70vh] overflow-y-auto"
				v-if="isStudent && studentInfo.student_name">
				<div class="flex flex-col gap-4">

					<!-- Header with editable avatar -->
					<div class="flex items-center border-b border-solid border-outline-gray-1 pb-4 gap-2">
						<div class="relative group flex-shrink-0">
							<Avatar size="3xl" class="h-12 w-12" :label="studentInfo.student_name"
								:image="editImage || studentInfo.image || null" />
							<FileUploader :fileTypes="['image/*']" :validate-file="validateFileSize" @success="(f) => { editImage = f.file_url }">
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
							<p class="text-ink-gray-6">{{ studentInfo.student_email_id }}</p>
						</div>
					</div>

					<!-- Success message -->
					<div v-if="saveSuccess"
						class="flex items-center gap-2 rounded-md bg-surface-green-1 px-3 py-2 text-sm text-ink-green-3">
						<FeatherIcon name="check-circle" class="h-4 w-4 flex-shrink-0" />
						{{ __('Profile saved successfully.') }}
					</div>

					<!-- Editable: Mobile -->
					<div>
						<label class="text-sm text-ink-gray-6">{{ __('Mobile Number') }}</label>
						<input v-model="editMobile" type="text"
							class="mt-1 w-full rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9 focus:outline-none focus:ring-1 focus:ring-blue-500" />
					</div>

					<!-- Editable: Address -->
					<div class="flex flex-col gap-2">
						<label class="text-sm text-ink-gray-6">{{ __('Address') }}</label>
						<input v-model="editAddr.address_line_1" type="text" :placeholder="__('Address Line 1')"
							class="w-full rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9 focus:outline-none focus:ring-1 focus:ring-blue-500" />
						<input v-model="editAddr.address_line_2" type="text" :placeholder="__('Address Line 2')"
							class="w-full rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9 focus:outline-none focus:ring-1 focus:ring-blue-500" />
						<div class="grid grid-cols-3 gap-2">
							<input v-model="editAddr.city" type="text" :placeholder="__('City')"
								class="rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9 focus:outline-none focus:ring-1 focus:ring-blue-500" />
							<input v-model="editAddr.state" type="text" :placeholder="__('State')"
								class="rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9 focus:outline-none focus:ring-1 focus:ring-blue-500" />
							<input v-model="editAddr.pincode" type="text" :placeholder="__('Pincode')"
								class="rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9 focus:outline-none focus:ring-1 focus:ring-blue-500" />
						</div>
						<input v-model="editAddr.country" type="text" :placeholder="__('Country')"
							class="w-full rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9 focus:outline-none focus:ring-1 focus:ring-blue-500" />
					</div>

					<!-- Appearance preference -->
					<div>
						<label class="text-sm text-ink-gray-6">{{ __('Appearance') }}</label>
						<div class="mt-1 flex gap-2 px-1">
							<button type="button" @click="setTheme('light')"
								:class="theme === 'light' ? 'ring-2 ring-blue-500' : ''"
								class="flex-1 rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9">
								{{ __('Light') }}
							</button>
							<button type="button" @click="setTheme('dark')"
								:class="theme === 'dark' ? 'ring-2 ring-blue-500' : ''"
								class="flex-1 rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9">
								{{ __('Dark') }}
							</button>
						</div>
					</div>

					<!-- Language preference -->
					<div>
						<label class="text-sm text-ink-gray-6">{{ __('Language') }}</label>
						<select v-model="selectedLanguage"
							class="mt-1 w-full rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9 focus:outline-none focus:ring-1 focus:ring-blue-500">
							<option value="">{{ __('Default') }}</option>
							<option v-for="lang in languages" :key="lang.language_code" :value="lang.language_code">
								{{ lang.language_name }}
							</option>
						</select>
						<p class="mt-1 text-xs text-ink-gray-4">
							{{ __('Available languages are configured by your seminary administrator.') }}
						</p>
					</div>

					<!-- Career / Job Board (saved to the Person spine, shared with the job board) -->
					<div class="border-t border-outline-gray-1 pt-3">
						<CareerProfileFields ref="career" />
					</div>

					<!-- Read-only fields -->
					<div class="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
						<div v-for="field in readOnlyFields" :key="field.label" class="flex">
							<span class="text-ink-gray-5 w-32 flex-shrink-0">{{ field.label }}:</span>
							<span class="text-ink-gray-9">{{ field.value }}</span>
						</div>
					</div>

					<!-- Note with support mailto -->
					<div class="flex items-start bg-surface-gray-1 p-2 text-ink-gray-6 text-sm rounded-md">
						<FeatherIcon name="info" class="h-4 w-4 mr-2 flex-shrink-0 mt-0.5" />
						<span>
							{{ __('In case of any incorrect details, please contact') }}
							<a v-if="supportUser" :href="`mailto:${supportUser}`" class="text-ink-blue-link underline ml-1">
								{{ __(' the school admin') }}</a>
							<span v-else>{{ __(' the school admin') }}</span>.
						</span>
					</div>
				</div>
			</div>

			<!-- Instructor view (editable) -->
			<div class="profile-dialog text-base text-ink-gray-9 max-h-[70vh] overflow-y-auto" v-else-if="isInstructor">
				<div class="flex flex-col gap-4">
					<div class="flex items-center border-b border-solid border-outline-gray-1 pb-4 gap-2">
						<div class="relative group flex-shrink-0">
							<Avatar size="3xl" class="h-12 w-12" :label="instructorInfo.instructor_name"
								:image="editProfileImage || instructorInfo.profileimage || null" />
							<FileUploader :fileTypes="['image/*']" :validate-file="validateFileSize" @success="(f) => { editProfileImage = f.file_url }">
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
							<p class="text-lg font-semibold">{{ instructorInfo.instructor_name }}</p>
							<p class="text-ink-gray-6">{{ instructorInfo.user }}</p>
						</div>
					</div>
					<div v-if="saveSuccess"
						class="flex items-center gap-2 rounded-md bg-surface-green-1 px-3 py-2 text-sm text-ink-green-3">
						<FeatherIcon name="check-circle" class="h-4 w-4 flex-shrink-0" />
						{{ __('Profile saved successfully.') }}
					</div>
					<div class="flex flex-col gap-3">
						<div>
							<label class="text-sm text-ink-gray-6">{{ __('Name') }}</label>
							<input v-model="editName" type="text"
								class="mt-1 w-full rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9 focus:outline-none focus:ring-1 focus:ring-blue-500" />
						</div>
						<div>
							<label class="text-sm text-ink-gray-6">{{ __('Short Bio') }}</label>
							<input v-model="editShortbio" type="text"
								class="mt-1 w-full rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9 focus:outline-none focus:ring-1 focus:ring-blue-500" />
						</div>
						<div>
							<label class="text-sm text-ink-gray-6 mb-1 block">{{ __('Bio') }}</label>
							<LightEditor
								id="instructor-bio"
								:content="editBio"
								:placeholder="__('Write your bio...')"
								@change="(val) => (editBio = val)"
							/>
						</div>
						<!-- Appearance preference -->
						<div>
							<label class="text-sm text-ink-gray-6">{{ __('Appearance') }}</label>
							<div class="mt-1 flex gap-2 px-1">
								<button type="button" @click="setTheme('light')"
									:class="theme === 'light' ? 'ring-2 ring-blue-500' : ''"
									class="flex-1 rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9">
									{{ __('Light') }}
								</button>
								<button type="button" @click="setTheme('dark')"
									:class="theme === 'dark' ? 'ring-2 ring-blue-500' : ''"
									class="flex-1 rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9">
									{{ __('Dark') }}
								</button>
							</div>
						</div>
						<!-- Language preference -->
						<div>
							<label class="text-sm text-ink-gray-6">{{ __('Language') }}</label>
							<select v-model="selectedLanguage"
								class="mt-1 w-full rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9 focus:outline-none focus:ring-1 focus:ring-blue-500">
								<option value="">{{ __('Default') }}</option>
								<option v-for="lang in languages" :key="lang.language_code" :value="lang.language_code">
									{{ lang.language_name }}
								</option>
							</select>
							<p class="mt-1 text-xs text-ink-gray-4">
								{{ __('Available languages are configured by your seminary administrator.') }}
							</p>
						</div>
						<!-- Communication Preferences -->
						<div class="border-t border-outline-gray-1 pt-3 mt-1">
							<p class="text-sm font-semibold text-ink-gray-7 mb-2">{{ __('Communication Preferences') }}</p>
							<div>
								<label class="text-sm text-ink-gray-6">{{ __('E-mail for student contact') }}</label>
								<input v-model="editProfEmail" type="email"
									class="mt-1 w-full rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9 focus:outline-none focus:ring-1 focus:ring-blue-500" />
							</div>
							<div class="mt-2">
								<label class="text-sm text-ink-gray-6">{{ __('Phone for messaging') }}</label>
								<input v-model="editPhoneMessage" type="tel"
									class="mt-1 w-full rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9 focus:outline-none focus:ring-1 focus:ring-blue-500" />
							</div>
							<div class="mt-2">
								<label class="text-sm text-ink-gray-6">{{ __('WhatsApp number') }}</label>
								<input v-model="editWhatsapp" type="tel" placeholder="+15551234567"
									class="mt-1 w-full rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9 focus:outline-none focus:ring-1 focus:ring-blue-500" />
								<p class="mt-1 text-xs text-ink-gray-4">
									{{ __('Shown as a WhatsApp contact icon. Other channels (e.g. Telegram) are managed on your Communication Preferences page.') }}
								</p>
							</div>
							<label class="mt-3 flex items-center gap-2 text-sm text-ink-gray-7 cursor-pointer">
								<input type="checkbox" v-model="editStudentsMayContact" />
								{{ __('Students may contact me') }}
							</label>
							<p class="text-xs text-ink-gray-4">
								{{ __('When off, only staff can reach you through the portal; students see no contact icons on your courses.') }}
							</p>
						</div>
					</div>
				</div>
			</div>

			<!-- Fallback view: users who are neither student nor instructor (e.g. Partners) -->
			<div class="profile-dialog text-base text-ink-gray-9 max-h-[70vh] overflow-y-auto"
				v-else-if="!isStudent && !isInstructor">
				<div class="flex flex-col gap-4">
					<div class="flex items-center border-b border-solid border-outline-gray-1 pb-4 gap-2">
						<Avatar size="3xl" class="h-12 w-12" :label="userResource.data?.full_name"
							:image="userResource.data?.user_image || null" />
						<div class="flex flex-col ml-2 gap-1">
							<p class="text-lg font-semibold">{{ userResource.data?.full_name }}</p>
							<p class="text-ink-gray-6">{{ userResource.data?.email }}</p>
						</div>
					</div>
					<!-- Appearance preference -->
					<div>
						<label class="text-sm text-ink-gray-6">{{ __('Appearance') }}</label>
						<div class="mt-1 flex gap-2 px-1">
							<button type="button" @click="setTheme('light')"
								:class="theme === 'light' ? 'ring-2 ring-blue-500' : ''"
								class="flex-1 rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9">
								{{ __('Light') }}
							</button>
							<button type="button" @click="setTheme('dark')"
								:class="theme === 'dark' ? 'ring-2 ring-blue-500' : ''"
								class="flex-1 rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9">
								{{ __('Dark') }}
							</button>
						</div>
					</div>
					<!-- Language preference -->
					<div>
						<label class="text-sm text-ink-gray-6">{{ __('Language') }}</label>
						<select v-model="selectedLanguage"
							class="mt-1 w-full rounded-md border border-outline-gray-2 px-3 py-2 text-sm bg-surface-white text-ink-gray-9 focus:outline-none focus:ring-1 focus:ring-blue-500">
							<option value="">{{ __('Default') }}</option>
							<option v-for="lang in languages" :key="lang.language_code" :value="lang.language_code">
								{{ lang.language_name }}
							</option>
						</select>
						<p class="mt-1 text-xs text-ink-gray-4">
							{{ __('Available languages are configured by your seminary administrator.') }}
						</p>
					</div>
				</div>
			</div>

		</template>
	</Dialog>
</template>

<script setup>
import { Dialog, Avatar, FeatherIcon, FileUploader, createResource } from 'frappe-ui'
import { ref, computed, watchEffect } from 'vue'
import { validateFileSize } from '@/utils'
import { usersStore } from '../stores/user'
import LightEditor from '@/components/LightEditor.vue'
import CareerProfileFields from '@/components/CareerProfileFields.vue'
import { useTheme } from '@/composables/useTheme'

const { theme, setTheme } = useTheme()

const { userResource } = usersStore()

const showProfileDialog = defineModel({ default: false })

// ── Shared ────────────────────────────────────────────────────────────────────
const isStudent = ref(false)
const isInstructor = ref(false)
const user = ref('')
const saveSuccess = ref(false)

const handleClose = (close) => {
	showProfileDialog.value = false
	saveSuccess.value = false
	close?.()
}

// ── Language ─────────────────────────────────────────────────────────────────
const selectedLanguage = ref('')
const originalLanguage = ref('')
const languages = ref([])

const languageResource = createResource({
	url: 'seminary.seminary.api.get_enabled_languages',
	auto: true,
	onSuccess(data) {
		languages.value = data.languages || []
		selectedLanguage.value = data.current || ''
		originalLanguage.value = data.current || ''
	},
})

const saveLanguageResource = createResource({
	url: 'seminary.seminary.api.set_user_language',
})

const languageChanged = computed(() => selectedLanguage.value !== originalLanguage.value)

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

const career = ref(null)
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
		if (languageChanged.value) {
			setTimeout(() => window.location.reload(), 1000)
		} else {
			setTimeout(() => handleClose(), 1000)
		}
	},
	onError(err) {
		console.error(err.messages?.[0] || err)
	},
})

const saveStudent = () => {
	if (languageChanged.value) {
		saveLanguageResource.submit({ language: selectedLanguage.value })
	}
	// Career fields live on the Person spine; the dialog's single Save covers them too.
	career.value?.save()
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
	prof_email: '', phone_message: '', whatsapp: '', students_may_contact: 1,
})

const editName = ref('')
const editShortbio = ref('')
const editBio = ref('')
const editProfEmail = ref('')
const editPhoneMessage = ref('')
const editWhatsapp = ref('')
const editStudentsMayContact = ref(true)
const editProfileImage = ref('')

const saveInstructorResource = createResource({
	url: 'seminary.seminary.api.save_instructor_profile',
	onSuccess(data) {
		Object.assign(instructorInfo.value, data)
		saveSuccess.value = true
		if (languageChanged.value) {
			setTimeout(() => window.location.reload(), 1000)
		} else {
			setTimeout(() => handleClose(), 1000)
		}
	},
	onError(err) {
		console.error(err.messages?.[0] || err)
	},
})

const saveInstructor = () => {
	if (languageChanged.value) {
		saveLanguageResource.submit({ language: selectedLanguage.value })
	}
	saveInstructorResource.submit({
		instructor_name: editName.value,
		shortbio: editShortbio.value,
		bio: editBio.value || '',
		prof_email: editProfEmail.value,
		phone_message: editPhoneMessage.value,
		whatsapp: editWhatsapp.value,
		students_may_contact: editStudentsMayContact.value ? 1 : 0,
		profileimage: editProfileImage.value || null,
	})
}

// ── Other users (e.g. Partners): universal preferences only ──────────────────
const savePreferences = () => {
	if (languageChanged.value) {
		saveLanguageResource.submit(
			{ language: selectedLanguage.value },
			{ onSuccess: () => window.location.reload() }
		)
	} else {
		handleClose()
	}
}

// ── Bootstrap resources when user data is available ──────────────────────────
const studentResource = ref(null)
const instructorResource = ref(null)

watchEffect(() => {
	if (!userResource.data) return
	isStudent.value = userResource.data.is_student
	isInstructor.value = userResource.data.is_instructor
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

	if (isInstructor.value && !instructorResource.value) {
		instructorResource.value = createResource({
			url: 'seminary.seminary.api.get_instructor_info',
			auto: true,
			onSuccess(response) {
				Object.assign(instructorInfo.value, response)
				editName.value = response.instructor_name || ''
				editShortbio.value = response.shortbio || ''
				editBio.value = response.bio || ''
				editProfEmail.value = response.prof_email || ''
				editPhoneMessage.value = response.phone_message || ''
				editWhatsapp.value = response.whatsapp || ''
				editStudentsMayContact.value = response.students_may_contact !== 0
				editProfileImage.value = response.profileimage || ''
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
			onClick: isStudent.value ? saveStudent : (isInstructor.value ? saveInstructor : savePreferences),
		},
		{
			label: __('Close'),
			variant: 'ghost',
			onClick: (close) => handleClose(close),
		},
	],
}))
</script>
