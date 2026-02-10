<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
	</header>
    <div class="md:w-3/4 md:mx-auto py-5 mx-5">
		<div class="grid grid-cols-3 gap-5 mb-5">
			<!-- Custom Dropdown for Exams -->
  <div>
    <label for="examDropdown" class="block text-sm font-medium text-gray-700">
      {{ __('Exam') }}
    </label>
    <select
      id="examDropdown"
      v-model="examID"
      class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
    >
      <option value="">{{ __('All Exams') }}</option>
      <option
        v-for="exam in filteredExams"
        :key="exam.value"
        :value="exam.value"
      >
        {{ exam.label }}
      </option>
    </select>
  </div>
		  <!-- Existing Student Filter -->
          <div>
    <label for="studentDropdown" class="block text-sm font-medium text-gray-700">
      {{ __('Student') }}
    </label>
    <Link
      id="studentDropdown"
      doctype="User"
      v-model="member"
      :placeholder="__('Student')"
    />
  </div>

  <!-- Existing Status Filter -->
  <div>
    <label for="statusDropdown" class="block text-sm font-medium text-gray-700">
      {{ __('Status') }}
    </label>
    <FormControl
      id="statusDropdown"
      v-model="status"
      type="select"
      :options="statusOptions"
      :placeholder="__('Status')"
    />
  </div>

		</div>
        </div>
	<div v-if="submissions.loading || submissions.data?.length" class="w-full">

		<ListView
			:columns="examColumns"
			:rows="submissions.data"
            :options="{selectable: false}"
			row-key="name"

		>
			<ListHeader
				class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
			>
				<ListHeaderItem :item="item" v-for="item in examColumns">
				</ListHeaderItem>
			</ListHeader>
			<ListRows>
				<router-link
					v-for="row in submissions.data"
					:to="{
						name: 'ExamSubmission',
						params: {
							submission: row.name,
						},
					}"
				>
                <ListRow :row="row">
						<template #default="{ column, item }">
							<ListRowItem :item="row[column.key]" :align="column.align">
								<div v-if="column.key == 'status'">
									<Badge :theme="getStatusTheme(row[column.key])">
										{{ row[column.key] }}
									</Badge>
								</div>
								<div v-else>
									{{ row[column.key] }}
								</div>
							</ListRowItem>
						</template>
					</ListRow>
				</router-link>
			</ListRows>
		</ListView>
		<div class="flex justify-center my-5">
			<Button v-if="submissions.hasNextPage" @click="submissions.next()">
				{{ __('Load More') }}
			</Button>
		</div>
	</div>
    <div
			v-else
			class="text-center p-5 text-ink-gray-5 mt-52 w-3/4 md:w-1/2 mx-auto space-y-2"
		>
			<BookOpenCheck class="size-8 mx-auto stroke-1 text-ink-gray-4" />
			<div class="text-xl font-medium">
				{{ __('No submissions') }}
			</div>
			<div class="leading-5">
				{{ __('There are no submissions for this course.') }}
			</div>
		</div>

    <div class="mt-10">
  <h2 class="text-lg font-semibold mb-4">{{ __('Students with No Submissions') }}</h2>
  <table class="table-auto border-collapse w-full">
    <thead>
      <tr class="bg-gray-100">
        <th class="border px-4 py-2">{{ __('Student Name') }}</th>
        <th class="border px-4 py-2">{{ __('Program') }}</th>
        <th class="border px-4 py-2">{{ __('Email') }}</th>
        <th class="border px-4 py-2">{{ __('Exam') }}</th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="student in notSubmittedStudents"
        :key="student.stuemail_rc"
        class="hover:bg-gray-50"
      >
        <td class="border px-4 py-2">{{ student.stuname_roster}}</td>
        <td class="border px-4 py-2">{{ student.program_std_scr }}</td>
        <td class="border px-4 py-2">
          <a :href="`mailto:${student.email}`" class="text-blue-500 underline">
            {{ student.stuemail_rc }}
          </a>
        </td>
        <td class="border px-4 py-2">{{ student.exam}}</td>
      </tr>
    </tbody>
  </table>
</div>
</template>
<script setup>
import {
	Badge,
	Breadcrumbs,
    Button,
	createListResource,
	FormControl,
	ListView,
	ListHeader,
	ListHeaderItem,
	ListRows,
	ListRow,
	ListRowItem,
    createResource
} from 'frappe-ui'
import { computed, onMounted, inject, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { BookOpenCheck } from 'lucide-vue-next'
import Link from '@/components/Controls/Link.vue'
import Exam from '../components/Exam.vue'
const dayjs = inject('$dayjs')
const router = useRouter()
const user = inject('$user')
const examID = ref('')
const member = ref('')
const status = ref('')



const props = defineProps({
	examID: {
		type: String,
		required: false,
	},
    courseName: {
        type: String,
        required: true,
    },
})
onMounted(() => {
	if (!user.data?.is_instructor && !user.data?.is_moderator) {
		router.push({ name: 'Courses' })
	}
    examID.value = props.examID || router.currentRoute.value.params.examID
    member.value = router.currentRoute.value.query.member
	status.value = router.currentRoute.value.query.status

    reloadSubmissions()
    fetchNotSubmittedStudents()
})

const notSubmittedStudents = ref([]); // Array to store students who didn't submit

// Fetch students who didn't submit the assignment
const fetchNotSubmittedStudents = async () => {
  try {
    const response = await fetch(`/api/method/seminary.seminary.utils.missing_exams?course=${props.courseName}`);
    const data = await response.json();
    console.log('Fetched data:', data);

    // Filter students who didn't submit the assignment
    if (!examID.value) {
      notSubmittedStudents.value = data.message;
      return;
    } else {
      notSubmittedStudents.value = data.message.filter(student => student.exam === examID.value);
    }

  } catch (error) {
    console.error('Error fetching not submitted students:', error);
  }
};

const examlist = createResource({
  url: '/api/method/seminary.seminary.utils.get_course_exams',
  params: {
    course: props.courseName,
  },
  auto: true,
  onSuccess(data) {
    console.log('Examlist fetched successfully:', data);
  },
  onError(error) {
    console.error('Error fetching examlist:', error);
  },
});

const filteredExams = computed(() => {
  console.log('Exam list:', examlist.data);
  return examlist.data?.map((exam) => ({
    label: exam.title, // Use the `title` field for display
    value: exam.exam,  // Use the `exam` field as the value
  })) || [];
});
console.log('Filtered exams:', filteredExams);
const getExamFilters = () => {
	let filters = {
    course: props.courseName, // Add filter for course_schedule
  };
	if (examID.value) {
		filters.exam = examID.value
	}
	if (member.value) {
		filters.member = member.value
	}
	if (status.value) {
		filters.status = status.value
	}
	return filters
}
// watch changes in examID, member, and status and if changes in any then reload submissions. Also update the url query params for the same
watch([examID, member, status], () => {
	router.push({
		query: {
			examID: examID.value,
			member: member.value,
			status: status.value,
		},
	})
	reloadSubmissions()
    fetchNotSubmittedStudents()
})

const reloadSubmissions = () => {
	submissions.update({
		filters: getExamFilters(),
	})
	submissions.reload()
}

const submissions = createListResource({
	doctype: 'Exam Submission',
	filters: {
		exam: props.examID,
	},
	fields: ['name', 'member_name', 'score', 'percentage', 'exam_title', 'creation', 'fudge_points', 'status', 'time_taken'],
	filters: getExamFilters(),
    orderBy: 'creation desc',
    transform(data) {
		return data.map((row) => {
			return {
				...row,
				creation: dayjs(row.creation).fromNow(),
                score: String(row.score), // Convert score to String
                percentage: String(row.percentage), // Convert percentage to String
                time_taken: formatTimer(row.time_taken), // Format time taken
                fudge_points: String(row.fudge_points), // Convert fudge points to String
			}
		})
	},
})

// Format timer
const formatTimer = (seconds) => {
  const mins = Math.floor(seconds / 60).toString().padStart(2, '0');
  const secs = (seconds % 60).toString().padStart(2, '0');
  return `${mins}:${secs}`;
};

const course = createResource({
	url: 'seminary.seminary.utils.get_course_details',
	cache: ['course', props.courseName],
	params: {
		course: props.courseName,
	},
	auto: true,
}) //Neded for the breadcrumbs

const examColumns = computed(() => {
	return [
		{
			label: __('Student'),
			key: 'member_name',
			width: 1,
		},
        {
            label: __('Exam'),
            key: 'exam_title',
            width: 1,
        },
        {
            label: __('Status'),
            key: 'status',
            width: 1,
            align: 'center',

        },
		{
			label: __('Score'),
			key: 'score',
			width: 1,
			align: 'center',
		},
        {
            label: __('Fudge Points'),
            key: 'fudge_points',
            width: 1,
            align: 'center',
        },
        {
            label: __('Time Taken'),
            key: 'time_taken',
            width: 1,
            align: 'center',
        },
        {
            label: __('Submitted'),
            key: 'creation',
            width: 1,
            align: 'center',
        },
		{
			label: __('Percentage'),
			key: 'percentage',
			width: 1,
			align: 'center',
		},
	]
})

const statusOptions = computed(() => {
	return [
		{ label: '', value: '' },
		{ label: __('Not Graded'), value: 'Not Graded' },
		{ label: __('Graded'), value: 'Graded' },
	]
})
const getStatusTheme = (status) => {
	if (status === 'Graded') {
		return 'green'
	} else if (status === 'Not Graded') {
		return 'orange'
	} else {
		return 'red'
	}
}
const breadcrumbs = computed(() => {
	let items = [{ label: __('Courses'), route: { name: 'Courses' } }]
	items.push({
		label: course?.data?.course,
		route: { name: 'CourseDetail', params: { courseName: props.courseName } },
	})
    items.push({
        label: __('Gradebook'),
        route: { name: 'Gradebook', params: { courseName: props.courseName}  },
    })
    items.push({
        label: __('Exam Submissions'),
    })
	return items
})
</script>
