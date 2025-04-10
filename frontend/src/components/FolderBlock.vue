<template>

        <div class="flex flex-col border-2 border-gray-200 rounded-lg p-4 mb-4">
      <h4>Files in {{ props.folder.folder }}</h4>
      <ul>
        <div v-if="!files" class="mb-4">No files found in this folder.</div>
        <li v-for="file in files" :key="file.file_url" class="flex items-center mb-4">
          <a :href="file.file_url" download class="flex-1">{{ file.file_name }}</a>
        </li>
      </ul>
    </div>
       
</template>
<script setup>
import { inject, onMounted, ref } from 'vue'
import { Button, createResource } from 'frappe-ui'
import Folder from '@/components/FolderPlugin.vue'


const files = ref([]);

const props = defineProps({
	folder: {
		type: Object,
		required: true,
	},
	
})

console.log('folder', props.folder.folder)

onMounted(() => {
  fetchFiles();
});

const fetchFiles = async () => {

  try {

    const FilesInFolder = createResource({
      url: 'seminary.api.folder_upload.get_files_in_folder',
      params: {
        foldername: props.folder.folder,
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

const redirectToLogin = () => {
	window.location.href = `/login`
}
</script>
