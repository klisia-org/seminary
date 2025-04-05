<template>
  <div class="border-2 rounded-md min-w-80 p-5">
    <div class="text-3xl font-semibold text-ink-gray-9 text-center">
      
						{{ __("To Do") }}
					</div>
    <div v-if ="course.data.course && isStudent" class="text-ink-gray-7">
    

    
    <section v-if="missingAssessments.data" class="missing-assessments mt-4">
      <h3 class="text-xl font-semibold text-ink-gray-9">{{__("Missing Assessments") }}</h3>
      <ul>
        <li v-for="assessment in missingAssessments.data" :key="assessment.id" class="text-ink-gray-7">
           {{ assessment.title }} (Due: {{ formatDate(assessment.due_date) }})
        </li>
      </ul>
    </section> 
    </div>
    <section v-if="Assessments && Assessments.data && Assessments.data.length" class="due-soon mt-4">
        <h3>Due Soon</h3>
        <ul>
            <li 
                v-for="assessment in (Assessments.data || []).filter(a => new Date(a.due_date) >= new Date()).slice(0, 5)" 
                :key="assessment.id"
            >
                {{ assessment.title }} (Due: {{ formatDate(assessment.due_date) }})
            </li>
        </ul>
    </section>
    <section v-if="!missingAssessments.data && !Assessments.data" class="no-assessments mt-4">
        <h3 class="text-xl font-semibold text-ink-gray-9">{{__("Congrats! No assessments for now.") }}</h3>
        
    </section>
   
  </div> 
</template> 

<script setup>
import { Button, createResource, Tooltip } from 'frappe-ui'
import { showToast, formatAmount } from '@/utils/'
import { computed, inject, ref } from 'vue'
import { useRouter } from 'vue-router'
import { usersStore } from '../stores/user'
import dayjs from '@/utils/dayjs'

const router = useRouter()
const user = inject('$user')
let userResource = usersStore()

let isStudent = user.data.is_student
let isInstructor = user.data.is_instructor

const props = defineProps({
	course: {
		type: String,
		required: true,
	},
})

const course = createResource({
	url: 'seminary.seminary.utils.get_course_details',
	cache: ['course', props.course],
	params: {
		course: props.course,
	},
	auto: true,
})


const Assessments = createResource({
    url: 'seminary.seminary.utils.get_assessments',
    cache: ['assessments', props.course],
    params: {
        course: props.course,
        
    },
   
})

const formatDate = (date) => {
    return dayjs(date).fromNow()
}


const missingAssessments = createResource({
    url: 'seminary.seminary.utils.get_missingassessments',
    cache: ['missingassessments', props.course],
    params: {
        course: props.course,
        member: user.data?.name,
    },
    
})

</script>

<style scoped>
.course-card-todo {
  padding: 1rem; 
  border: 1px solid #ccc;
  border-radius: 8px;
  background-color: #f9f9f9;
}

h2 {
  margin-bottom: 1rem;
}

section {
  margin-bottom: 1.5rem;
}

ul {
  list-style: none;
  padding: 0;
}

li {
  margin-bottom: 0.5rem;
}

a {
  color: #007bff;
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}
</style>