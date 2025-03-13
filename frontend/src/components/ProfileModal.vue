<template>
	<Dialog
		v-model="showProfileDialog"
		:options="{
			title: 'Profile',
			size: 'xl',
		  }"
	>
	<template #body-content>
			<div class="text-base" v-if="isStudent && studentInfo.student_name">
				<div class="flex flex-col gap-4">
					<div class="flex items-center border-b border-solid border-lightGray pb-4 gap-2">
					  <Avatar
						size="3xl"
						class="h-12 w-12"
						:label="studentInfo.student_name"
						:image="studentInfo.image || null"
					  />
					  <div class="flex flex-col ml-2 gap-1">
						<p class="text-lg font-semibold">{{ studentInfo.student_name }}</p>
						<p class="text-gray-600">{{ studentInfo.student_email_id }}</p>
					  </div>
					</div>
				  	<div>
						<div class="flex gap-4">
							<div v-for="section in infoFormat" :key="section.section" class="flex-1 flex flex-col gap-4">
								<div v-for="field in section.fields" :key="field.label" >
									<div class="flex items-center" v-if="field.label !== 'Address' ">
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
					  In case of any incorrect details, please contact the school admin.
					</div>
				</div>				  
			</div>
			<div class="text-base" v-else-if="!isStudent && instructorInfo.instructor_name">
				<div class="flex flex-col gap-4">
					<div class="flex items-center border-b border-solid border-lightGray pb-4 gap-2">
					  <Avatar
						size="3xl"
						class="h-12 w-12"
						:label="instructorInfo.instructor_name"
						:image="instructorInfo.image || null"
					  />
					  <div class="flex flex-col ml-2 gap-1">
						<p class="text-lg font-semibold">{{ instructorInfo.instructor_name }}</p>
						<p class="text-gray-600">{{ instructorInfo.user }}</p>
					  </div>
					</div>
				  	<div>
						<div class="flex gap-4">
							<div v-for="section in instructorInfoFormat" :key="section.section" class="flex-1 flex flex-col gap-4">
								<div v-for="field in section.fields" :key="field.label" >
									<div class="flex items-center">
										<p class="w-1/2 text-sm text-gray-600">{{ field.label }}:&nbsp;</p>
										<p class="w-1/2 text-gray-900" v-html="field.label === 'Bio' ? stripHtmlTags(field.value) : field.value"></p>
									</div>
								</div>
							</div>
						</div>
					</div>
				  
					<div class="flex items-center bg-gray-50 p-2 text-gray-600 text-sm rounded-md">
					  <FeatherIcon name="info" class="h-4 mr-2" />
					  In case of any incorrect details, please make the adjustments on the portal backend for now.
					</div>
				</div>				  
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { Dialog, Avatar, FeatherIcon, createResource } from 'frappe-ui'
import { inject, ref, computed, watchEffect } from 'vue'
import { usersStore } from '../stores/user'

let userResource = usersStore()

const showProfileDialog = inject('showProfileDialog')

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
					label: 'Mobile Number',
					value: studentInfo.value.student_mobile_number,
				},
				{
					label: 'Joining Date',
					value: studentInfo.value.joining_date,
				},
				{
					label: 'Date of Birth',
					value: studentInfo.value.date_of_birth,
				},
				{
					label: 'Address',
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
					label: 'Gender',
					value: studentInfo.value.gender
				},
				{
					label: 'Nationality',
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
})

const instructorInfoFormat = ref([])

watchEffect(() => {
    instructorInfoFormat.value = [
        {
            section: 'section 1',
            fields: [
                {
                    label: 'Instructor Name',
                    value: instructorInfo.value.instructor_name,
                },
                {
                    label: 'User',
                    value: instructorInfo.value.user,
                },
                {
                    label: 'Bio',
                    value: instructorInfo.value.bio,
                },
                {
                    label: 'Short Bio',
                    value: instructorInfo.value.shortbio,
                },
            ]
        },
    ]
})

// Watch for changes in userResource to set isStudent and user
const isStudent = ref(false)
const user = ref('')

watchEffect(() => {
	if (userResource.userResource.data) {
		isStudent.value = userResource.userResource.data.is_student
		user.value = userResource.userResource.data.name

		// Initialize studentResource if isStudent is true and studentResource is not already created
		if (isStudent.value && !studentResource.value) {
			studentResource.value = createResource({
				url: 'seminary.seminary.api.get_student_info',
				params: {
					student: user.value,
				},
				onSuccess: (response) => {
					Object.assign(studentInfo.value, response)
				},
				auto: true,
			})
		}

		// Initialize instructorResource if isStudent is false and instructorResource is not already created
		if (!isStudent.value && !instructorResource.value) {
			instructorResource.value = createResource({
				url: 'seminary.seminary.api.get_instructor_info',
				params: {
					instructor: user.value,
				},
				onSuccess: (response) => {
					Object.assign(instructorInfo.value, response)
				},
				auto: true,
			})
		}
	}
})

// Function to strip HTML tags from a string
function stripHtmlTags(str) {
	const div = document.createElement('div')
	div.innerHTML = str
	return div.textContent || div.innerText || ''
}

</script>