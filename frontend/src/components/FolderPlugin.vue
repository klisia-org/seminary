<template>
  <div class="Folder">
    <h3>Manage Course Folders</h3>
    <div>
      <label>
        <input type="radio" v-model="folderAction" value="select" />
        Select Existing Folder    
      </label>
      <label class="ml-4">
        <input type="radio" v-model="folderAction" value="create" />
        Create New Folder
      </label>
    </div>
    
    <div v-if="folderAction === 'select'" class="mt-4 mb-4">
      <Link 
        v-model="selectedFolder"
        doctype="Course Folder"
        options="foldername"
        :label="__('Select a folder')"
        
            
        />
    </div>

    <div v-if="folderAction === 'create'">
      <input type="text" v-model="newFolderName" placeholder="Enter folder name" />
      <Link
        v-model="course"
        doctype="Course"
        :label="__('Select a course')"
        />
      <button @click="createFolder">Create Folder</button>
    </div>

    <div v-if="selectedFolder" class="block mt-4">
      <h4>Files in {{ selectedFolder }}</h4>
      <ul>
        <div v-if="!files" class="mb-4">No files found in this folder.</div>
        <li v-for="file in files" :key="file.file_url" class="flex items-center mb-4">
          <a :href="file.file_url" download class="flex-1">{{ file.file_name }}</a>
          <Tooltip :text="__('Delete File')" placement="bottom">
            <Trash2
              @click.prevent="removeFile(file.file_url)"
              class="ml-4 h-4 w-4 text-red-500"
            />
          </Tooltip>
        </li>
      </ul>
      <input type="file" multiple @change="uploadFiles" />
    </div>
  </div>
</template>

<script setup>
import { createResource, Dialog, Button, Tooltip } from 'frappe-ui';
import { onMounted, ref, watch } from 'vue';
import Link from '@/components/Controls/Link.vue';
import { FolderTool } from '@/utils/foldertool'; // Corrected to named import
import { useRoute, useRouter } from 'vue-router';
import { Trash2 } from 'lucide-vue-next';

const route = useRoute();

const folderAction = ref('select');
const selectedFolder = ref(null);
const foldername = ref(''); // Declare foldername globally
const newFolderName = ref('');
const files = ref([]);
const folders = ref([]);
const course = ref(null);

const fetchCourse = async () => {
  const courseName = route.params.courseName;
  console.log("Course Name: ", courseName);
  if (courseName) {
    const resource = createResource({
      url: 'frappe.client.get_value',
      makeParams(values) {
        return {
          doctype: 'Course Schedule',
          fieldname: 'course',
          filters: {
            name: courseName,
          },
        };
      },
    });
    const result = await resource.fetch(); // Wait for the resource to fetch data
    course.value = result.course; // Assign the fetched course value
    console.log("Fetched Course: ", course.value);
  } else {
    console.error("Course name not found in route params");
  return null;
}};

const props = defineProps({
	onAddition: {
		type: Function,
		required: false,
	},
})

const addFolder = () => {
	if (foldername.value) {
        const folder = foldername.value;
        props.onAddition(folder);
        console.log("Updating props", props.onAddition);
    }}

const fetchFolders = async () => {
    if (!course.value) 
        fetchCourse();
   if (course.value) {
    const foldersResource = createResource({
      url: 'frappe.client.get_list',
      makeParams(values) {
        return {
          doctype: 'Course Folder',
          filters: {
            course: course.value,
          },
          fields: ['name', 'foldername'],
        };
      },
    })
    const result = await foldersResource.fetch(); // Wait for the resource to fetch data
    folders.value = result; // Assign the fetched folders to the folders ref
    console.log("Fetched Folders: ", folders.value);
    return folders.value;
  }}  

const createFolder = async () => {
  if (!newFolderName.value) return alert('Folder name is required');
  const tool = new FolderTool({});
  const folder = await tool.createCourseFolder(course.value, newFolderName.value);
  folders.value.push(folder);
  selectedFolder.value = folder.foldername;
  newFolderName.value = '';
};

const fetchFiles = async () => {
  if (!foldername.value) return; // Use globally available foldername

  try {
    console.log("Selected Folder (foldername): ", foldername.value);

    const FilesInFolder = createResource({
      url: 'seminary.api.folder_upload.get_files_in_folder',
      params: {
        foldername: foldername.value,
      },
      auto: true,
    });
    const filesResult = await FilesInFolder.fetch(); // Wait for the resource to fetch data
    files.value = filesResult; // Assign the fetched files to the files ref
    console.log("Fetched Files: ", files.value);
  } catch (error) {
    console.error("Error fetching files:", error);
  }
};

const uploadFiles = async (event) => {
  const uploadedFiles = event.target.files;
  console.log("Uploaded Files: ", uploadedFiles);

  if (!foldername.value) {
    return alert("Please select a folder first.");
  }

  try {
    console.log("Selected Folder (foldername): ", foldername.value);

    const formData = new FormData();
    for (const file of uploadedFiles) {
      formData.append('files', file); // Append each file individually
    }
    formData.append('foldername', foldername.value);
    console.log("Form Data:");
    for (const [key, value] of formData.entries()) {
      console.log(`${key}:`, value);
    }

    const response = await fetch('/api/method/seminary.api.folder_upload.upload_folder', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      console.error("Error uploading files:", error);
      alert(`Error: ${error.message || "Failed to upload files."}`);
      return;
    }

    console.log("Files uploaded successfully.");
    await fetchFiles(); // Refresh the file list after upload
  } catch (error) {
    console.error("Error uploading files:", error);
    alert("An error occurred while uploading files.");
  }
};

const removeFile = async (fileUrl) => {
  await fetch('seminary.api.folder_upload.delete_file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_url: fileUrl }),
    }).then((response) => response.json());

  await fetchFiles();
};

// Watch selectedFolder and update foldername
watch(selectedFolder, async (newFolder) => {
  if (newFolder) {
    try {
      const resource = createResource({
        url: 'frappe.client.get_value',
        makeParams(values) {
          return {
            doctype: 'Course Folder',
            fieldname: 'foldername',
            filters: {
              name: newFolder,
            },
          };
        },
      });
      const result = await resource.fetch();
      foldername.value = result.foldername; // Update foldername globally
      console.log("Updated foldername: ", foldername.value);
        await addFolder(); // Call addFolder with the updated foldername
      await fetchFiles(); // Fetch files for the updated folder
    } catch (error) {
      console.error("Error fetching foldername:", error);
    }
  } else {
    foldername.value = ''; // Reset foldername if no folder is selected
  }
});

onMounted(async () => {
  await fetchCourse(); // Ensure course is fetched before proceeding
  await fetchFolders(); // Fetch folders after course is available
});
</script>

<style scoped>
.Folder {
  margin: 20px;
  border: 2px solid #ccc;
  padding: 10px;
  border-radius: 5px;
}
</style>
