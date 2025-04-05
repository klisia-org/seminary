<template>
       <header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
			
		</header>
  <div class="flex flex-row h-full">
    <!-- Left Side: Course Schedule Meeting Dates -->
    <div class="w-1/4 p-4 border-r">
      <h2 class="text-lg font-semibold mb-4">{{ __('Course Schedule') }}</h2>
      <div class="flex flex-col space-y-2">
  <button
    v-for="meeting in meetingDates.data"
    :key="meeting.name"
    :disabled="new Date(meeting.cs_meetdate) > today"
    class="p-2 border rounded-md text-left flex justify-between items-center"
    :class="{ 'bg-gray-200': new Date(meeting.cs_meetdate) > today, 'bg-blue-100': selectedDate?.name === meeting.name }"
    @click="selectDate(meeting)"
    :title="new Date(meeting.cs_meetdate) > today ? __('Cannot set attendance of future dates') : ''"
  >
    <span>{{ formatDate(meeting.cs_meetdate) }}</span>
    <span v-if="meeting.attendance === '1'" class="text-green-500">
      <Check class="h-5 w-5" />
    </span>
  </button>
</div>
    </div>

    <!-- Right Side: Attendance for Selected Date -->
    <div class="w-3/4 p-4">
      <h2 class="text-lg font-semibold mb-4">
        {{ __('Attendance for: ') }} {{ selectedDate?.cs_meetdate || __('Select a date') }}
      </h2>

      <!-- Edit Attendance Button -->
      <div v-if="attendanceTaken" class="mb-4">
        <button
          class="p-2 bg-yellow-200 border rounded-md"
          @click="editAttendance"
          :title="__('All changes will be recorded for audit purposes')"
        >
          {{ __('Edit Attendance') }}
        </button>
      </div>

      <!-- Students Table -->
      <table v-if="selectedDate" class="min-w-full table-auto border-collapse">
        <thead>
          <tr>
            <th class="p-2 border">{{ __('Image') }}</th>
            <th class="p-2 border">{{ __('Student Name') }}</th>
            <th class="p-2 border">{{ __('Present') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="student in students.data" :key="student.student">
            <td class="p-2 border">
              <img :src="student.stuimage" alt="Student Image" class="h-10 w-10 rounded-full" />
            </td>
            <td class="p-2 border">{{ student.stuname_roster }}</td>
            <td class="p-2 border text-center">
              <input
                type="checkbox"
                v-model="attendance[student.student]"
                :disabled="selectedDate?.attendance"
              />
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Summary Above the Mark Attendance Button -->
      <div v-if="selectedDate" class="mb-4">
        <p class="text-lg font-semibold">
          {{ __('Summary: ') }}
          <span class="text-green-500">{{ presentCount }}</span> {{ __('Present') }},
          <span class="text-red-500">{{ absentCount }}</span> {{ __('Absent') }}
        </p>
      </div>

      <!-- Mark Attendance Button -->
      <div v-if="selectedDate" class="mt-4">
        <button
          class="p-2 bg-blue-500 text-white rounded-md"
          @click="markAttendance"
          :disabled="presentCount === 0 || selectedDate?.attendance"
        >
          {{ __('Mark Attendance') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { createResource, Breadcrumbs } from 'frappe-ui';
import { useRouter, useRoute } from 'vue-router'
import { showToast } from '@/utils'
import { Check} from 'lucide-vue-next'
const router = useRouter()
const route = useRoute()

const props = defineProps({
  courseName: {
    type: String,
    required: true,
  },
});

const today = new Date();
const selectedDate = ref(null);
const attendance = ref({});
const attendanceTaken = ref(false);
const editing = ref(false);

// Fetch meeting dates
const meetingDates = createResource({
  url: 'seminary.seminary.utils.get_course_meetingdates',
  makeParams() {
    return {
      course: props.courseName, // Pass the course name to the server-side method
    };
  },
  auto: true,
});
console.log("Meeting dates: ", meetingDates)
// Fetch students
const students = createResource({
  url: 'frappe.client.get_list',
  makeParams() {
    return {
      doctype: 'Scheduled Course Roster',
      filters: {
        course_sc: props.courseName,
      },
      fields: ['student', 'stuname_roster', 'stuimage'],
      order_by: 'stuname_roster asc',
    };
  },
  auto: true,
});

const formatDate = (date) => {
  try {
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }).format(new Date(date));
  } catch (error) {
    console.error('Error formatting date:', error);
    return date; // Fallback to the raw date if formatting fails
  }
};

// Fetch attendance for the selected date
const attendanceResource = createResource({
  url: 'frappe.client.get_list',
  makeParams() {
    return {
      doctype: 'Student Attendance',
      filters: {
        course_schedule: props.courseName,
        date: selectedDate?.cs_meetdate,
      },
      fields: ['student', 'status'],
    };
  },
  auto: false, // Do not fetch automatically; fetch when a date is selected
});
onMounted(() => {
  if (presentCount.value === 0) {
    editing.value = true; // Allow editing if no students are marked as present
  }
});

// Watch attendanceResource.data to populate attendance data
watch(
  () => attendanceResource.data,
  (data) => {
    if (data) {
      attendance.value = {};
      data.forEach((record) => {
        attendance.value[record.student] = record.status === 'Present';
      });
      attendanceTaken.value = data.length > 0;
    }
  }
);

// Select a date
const selectDate = async (meeting) => {
  selectedDate.value = meeting;
  editing.value = false;
  await attendanceResource.reload(); // Fetch attendance for the selected date
};

// Edit attendance
const editAttendance = () => {
  editing.value = true;
};

const presentCount = computed(() =>
  Object.values(attendance.value).filter((status) => status).length
);

const absentCount = computed(() =>
  Object.values(attendance.value).filter((status) => !status).length
);

watch(presentCount, (newCount) => {
  if (newCount === 0) {
    editing.value = true; // Allow editing if no students are marked as present
  }
});

// Mark attendance
const markAttendance = async () => {
  if (!students.data || students.data.length === 0) {
    console.error("Students data is not loaded.");
    return;
  }

  console.log("Attendance Value:", attendance.value);
  console.log("Students Data:", students.data);

  const studentsPresent = Object.keys(attendance.value)
    .filter((student) => attendance.value[student])
    .map((student) => {
      const studentData = students.data.find((s) => s.student === student);
      if (!studentData) {
        console.error(`Student not found in students.data: ${student}`);
        return null;
      }
      return {
        student,
        stuname_roster: studentData.stuname_roster,
      };
    })
    .filter((student) => student !== null);

  const studentsAbsent = Object.keys(attendance.value)
    .filter((student) => !attendance.value[student])
    .map((student) => {
      const studentData = students.data.find((s) => s.student === student);
      if (!studentData) {
        console.error(`Student not found in students.data: ${student}`);
        return null;
      }
      return {
        student,
        stuname_roster: studentData.stuname_roster,
      };
    })
    .filter((student) => student !== null);

  console.log("Students Present:", studentsPresent);


  try {
    const response = await fetch("/api/method/seminary.seminary.api.mark_attendance", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        course_schedule: props.courseName,
        date: selectedDate.value.cs_meetdate,
        students_present: studentsPresent,
        students_absent: studentsAbsent,
      }),
    });

    const result = await response.json();
    if (result.message === "success") {
      selectedDate.value.attendance = true; // Update locally
      await attendanceResource.reload(); // Refresh attendance
      showToast(__('Success'), __('Attendance saved successfully'), 'check');
    }
  } catch (error) {
    console.error("Error marking attendance:", error);
    showToast(__('Error'), __(err.messages?.[0] || 'An error occurred while saving'), 'x');
  }
};

const course = createResource({
	url: 'seminary.seminary.utils.get_course_details',
	cache: ['course', props.courseName],
	params: {
		course: props.courseName,
	},
	auto: true,
}) //Neded for the breadcrumbs

const breadcrumbs = computed(() => {
	let items = [{ label: 'Courses', route: { name: 'Courses' } }]
	items.push({
		label: course?.data?.course,
		route: { name: 'CourseDetail', params: { courseName: props.courseName } },
	})
    items.push({
        label: 'Attendance',
        route: { name: 'StudentAttendanceCS', params: { courseName: props.courseName} },
    })
	return items
})
</script>

<style scoped>
/* Add any necessary styles here */
</style>
