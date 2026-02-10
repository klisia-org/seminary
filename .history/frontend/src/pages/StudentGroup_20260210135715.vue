<template>
    <div v-if="course.data && instructors.data">
        <header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
		</header>
    <h1 class="text-2xl font-bold mb-4 ml-5">{{ __('Student Group Management for ' + course.data.course) }}</h1>
    <h2 class="text-l mb-12 ml-5">Student Groups are used to assign students to specific groups within the course, both for assigning grading to specific instructors and for organizing collaborative work.</h2>


  <div v-if="hasSavedGroups" class="student-group-page">
       <!-- Input for number of groups -->

    <!-- Table of Students and Groups -->

      <h2 class="text-xl font-bold mb-4 ml-5">Student Groups</h2>
					<ListView
						:columns="groupColumns"
						:rows="saved_groups.data.student_name"
						row-key="student_name"
						:options="{
							showTooltip: false,
                            selectable: false,
						}"
					>
						<ListHeader
							class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
						>
							<ListHeaderItem :item="item" v-for="item in groupColumns" />
						</ListHeader>
						<ListRows>
							<ListRow
								:row="row"
								v-slot="{ idx, column, item }"
								v-for="row in saved_groups.data"

								class="cursor-pointer"
							>
								<ListRowItem :item="item">
									<div class="text-xs">
										{{ item }}
									</div>
								</ListRowItem>
							</ListRow>
						</ListRows>
					</ListView>
    </div>
    <div v-else class="mt-8 ml-5">
     <div class="mb-4">
      <label for="groupCount" class="block text-lg font-medium text-gray-700 mb-4">
        How many student groups should be created?
      </label>
      <input
        id="groupCount"
        type="number"
        v-model="groupCount"
        :min="2"
        :max="course.data.enrollments"
        class="mt-1 mb-4 block w-full border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
      />
    </div>

    <!-- Instructor selection -->
    <div  v-if="hasInstructors" class="mb-4">
      <p class="text-lg font-medium text-gray-700 mb-2">
        Please, select the instructor for each group:
      </p>
      <div v-for="(group, index) in groupCount" :key="index" class="mb-2">
        <label :for="`instructor-${index}`" class="block text-sm font-medium text-gray-700">
          Group {{ index + 1 }} Instructor
        </label>
    	<FormControl
						v-model="selectedInstructors[index]"
						:label="__('Instructor')"
						type="select"
						:options="instructorOptions"
					/>
      </div>
    </div>
    <div v-else class="mb-4">
      <p class="text-lg font-medium text-gray-700 mb-2">
        Only one instructor is assigned to this course. Student groups will be created with instructor: {{ instructors.data[0].instructor_name }}
      </p>
    </div>

    <!-- Create Groups Button -->
    <Button
        :variant="'solid'"
        theme="gray"
        size="sm"
        :label="__('Create Groups')"
        :loading="false"
        @click="createGroups"
         :disabled="!canCreateGroups"

    </Button>
    </div>
    </div>


</template>

<script setup>
import { ref, computed, inject, watch } from 'vue';
import { createResource, Breadcrumbs, ListView, ListHeader, ListHeaderItem, ListRows, ListRow, ListRowItem, FormControl, Button } from 'frappe-ui'
import { useRouter, useRoute } from 'vue-router';
import Link from '@/components/Controls/Link.vue'
import { updateDocumentTitle } from '@/utils'

const router = useRouter();
const route = useRoute();
const user = inject('$user')

const props = defineProps({
	courseName: {
		type: String,
		required: true,
	},
})

const instructors = createResource({
  url: 'seminary.seminary.utils.get_instructors',
  params: {
    course: props.courseName,
  },
  auto: true,
});
 console.log("Instructors fetched:", instructors);

console.log("Course Name:", props.courseName);

const course = createResource({
  url: 'seminary.seminary.utils.get_course_details',
  cache: ['course', props.courseName],
  params: {
    course: props.courseName,
  },
  auto: true,
})

const saved_groups = createResource({
  url: 'seminary.seminary.utils.get_student_groups',
  cache: ['saved_groups', props.courseName],
  params: {
    course: props.courseName,
  },
  auto: true,
});

console.log("Course:", course);
console.log("Saved Groups:", saved_groups);

const hasInstructors = computed(() => instructors.data && instructors.data.length > 1);
const hasSavedGroups = computed(() => saved_groups.data && saved_groups.data.length > 0);

const breadcrumbs = computed(() => {
  let items = [{ label: __('Courses'), route: { name: 'Courses' } }]
  items.push({
    label: course?.data?.course,
    route: { name: 'CourseDetail', params: { courseName: props.courseName } },
  })
  items.push({
    label: 'Assessment',
    route: { name: 'CourseAssessment', params: { courseName: props.courseName } }
  })
  return items
})

const pageMeta = computed(() => {
  return {
    title: course?.data?.title,
    description: "Configuration of Student Groups for the course",
  }
})

updateDocumentTitle(pageMeta)

const groupCount = ref(2);
const selectedInstructors = ref([]);
const studentGroups = ref([]);

const groupColumns = computed(() => {
	return [
		{
			label: __('Student'),
			key: 'student_name',
			width: 2,
		},
		{
			label: __('Student Group'),
			key: 'student_group',
			width: 2,
		},
        {
			label: __('Instructor'),
			key: 'group_instructor',
			width: 2,
		},

	]
})

const canCreateGroups = computed(() => {
  return (
    groupCount.value > 1 &&
    groupCount.value <= course.data.enrollments &&
    ((hasInstructors.value &&
    selectedInstructors.value.length === groupCount.value) || !hasInstructors.value)
  );
});

const instructorOptions = computed(() => {
  console.log("Instructors Data in Computed:", instructors.data);

  // Transform instructors.data into the expected format for FormControl
  if (Array.isArray(instructors.data)) {
    return instructors.data.map((instructor) => ({
      label: instructor.instructor_name, // Adjust based on actual data structure
      value: instructor.user, // Adjust based on actual data structure
    }));
  }

  return Object.values(instructors.data || {}).map((instructor) => ({
    label: instructor.instructor_name , // Adjust based on actual data structure
    value: instructor.user, // Adjust based on actual data structure
  }));
});

console.log("Can Create Groups:", canCreateGroups.value);
console.log("Instructor Options Outside Computed:", instructorOptions.value);

const students = createResource({
	url: 'seminary.seminary.utils.get_roster',
	cache: ['roster', props.courseName],
	params: {
		course: props.courseName,
	},
	auto: true,
})
console.log("Students fetched:", students.data);


function createGroups() {
  try {
    console.log("Create Groups function called");


    // Ensure students.data is defined
    if (!students.data || !Array.isArray(students.data)) {
      throw new Error("Students data is not available or not an array.");
    }

    // Filter students based on audit_bool and active fields
    const filteredStudents = students.data.filter(
      (student) => student.audit_bool === 0 && student.active === 1
    );

    // Map to extract student id
    const studentData = filteredStudents.map((student) => ({
      member: student.student,

    }));

    // Log the resulting array
    console.log("Filtered and Transformed Students:", studentData);

    // Logic to distribute students evenly among groups
    const groups = Array.from({ length: groupCount.value }, () => []);
    studentData.forEach((student, index) => {
      groups[index % groupCount.value].push(student);
    });

    // Log the groups for debugging
    console.log("Formed Groups:", groups);

    // Logic to assign instructors and create groups
    groups.forEach((group, index) => {
      const groupName = `${course.data.name} ${selectedInstructors.value[index] || instructors.data[0].instructor_name} Group ${index + 1}`;
      const mentor = selectedInstructors.value[index] || instructors.data[0].instructor_name;
      console.log(`Creating group: ${mentor} ${groupName}`, group);
      // Call API to create group
      const group_creator = createResource({
	url: 'seminary.seminary.utils.create_student_group',
	cache: ['student_group', props.courseName],
	params: {
		course: props.courseName,
		group_name: groupName,
		group_instructor: mentor,
		members: group,
	},
	auto: true,
})
    });
  } catch (error) {
    console.error("Error in createGroups function:", error);
  }
}

// Watch for changes in instructors.data to debug its state
watch(
  () => instructors.data,
  (newValue) => {
    console.log("Instructors data changed:", newValue);
    console.log("Instructor Options Updated:", instructorOptions.value);
  }
);
</script>

<style>
.student-group-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}
</style>