<template>
  <div class="flex flex-col gap-4 rounded-lg border-2 border-outline-gray-1 p-4 mb-4">
    <div class="flex items-start justify-between gap-3">
      <div class="flex flex-col gap-1">
        <h4 class="text-lg font-semibold text-ink-gray-9">{{ currentFolderName || folderName }}</h4>
        <div class="text-sm text-ink-gray-6 flex flex-wrap items-center gap-1" v-if="breadcrumbStack.length">
          <template v-for="(crumb, index) in breadcrumbStack" :key="crumb.id || `${crumb.label}-${index}`">
            <button
              type="button"
              class="rounded px-1.5 py-0.5 transition hover:bg-ink-gray-2 hover:text-ink-gray-9"
              :class="index === breadcrumbStack.length - 1 ? 'font-medium text-ink-gray-8 cursor-default' : 'text-ink-gray-7'"
              @click="index === breadcrumbStack.length - 1 ? null : navigateToBreadcrumb(index)"
            >
              {{ crumb.label }}
            </button>
            <span v-if="index < breadcrumbStack.length - 1">/</span>
          </template>
        </div>
      </div>
      <button
        type="button"
        class="shrink-0 inline-flex items-center gap-1.5 rounded border border-outline-gray-2 px-3 py-1.5 text-sm font-medium text-ink-gray-8 transition hover:border-outline-gray-3 hover:bg-ink-gray-2 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="!canDownload || isDownloading"
        @click="downloadAll"
      >
        <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="7 10 12 15 17 10" />
          <line x1="12" y1="15" x2="12" y2="3" />
        </svg>
        {{ isDownloading ? __('Preparing…') : __('Download all') }}
      </button>
    </div>
    <div v-if="downloadError" class="rounded border border-outline-red-1 bg-surface-red-1 px-3 py-2 text-sm text-ink-red-3">
      {{ downloadError }}
    </div>

    <div v-if="errorMessage" class="rounded border border-outline-red-1 bg-surface-red-1 px-3 py-2 text-sm text-ink-red-3">
      {{ errorMessage }}
    </div>
    <div v-else-if="isLoading" class="text-sm text-ink-gray-6">
      {{ __('Loading folder contents…') }}
    </div>
    <template v-else>
      <section class="space-y-2">
        <h5 class="text-sm font-semibold text-ink-gray-9">{{ __('Sub-folders') }}</h5>
        <div v-if="!subfolders.length" class="text-sm text-ink-gray-5">
          {{ __('No sub-folders in this location.') }}
        </div>
        <ul v-else class="space-y-2">
          <li
            v-for="folder in subfolders"
            :key="folder.name"
            class="flex items-center justify-between rounded border border-outline-gray-2 px-3 py-2 transition hover:border-outline-gray-3"
          >
            <button
              type="button"
              class="text-left text-sm font-medium text-ink-blue-link hover:underline"
              @click="openSubfolder(folder)"
            >
              {{ folder.file_name }}
            </button>
            <span class="text-xs text-ink-gray-5">{{ __('Folder') }}</span>
          </li>
        </ul>
      </section>

      <section class="space-y-2">
        <h5 class="text-sm font-semibold text-ink-gray-9">{{ __('Files') }}</h5>
        <div v-if="!files.length" class="text-sm text-ink-gray-5">
          {{ __('No files available in this folder.') }}
        </div>
        <ul v-else class="space-y-2">
          <li
            v-for="file in files"
            :key="file.file_url || file.name"
            class="flex items-center gap-3 rounded border border-outline-gray-2 px-3 py-2 transition hover:border-outline-gray-3"
          >
            <a :href="file.file_url" download class="flex-1 truncate text-sm text-ink-blue-link hover:underline">
              {{ file.file_name }}
            </a>
            <span class="text-xs text-ink-gray-5">{{ humanFileSize(file.file_size) }}</span>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { createResource } from 'frappe-ui'

const props = defineProps({
  folder: {
    type: [Object, String],
    required: true,
  },
})

const folderName = computed(() => {
  if (typeof props.folder === 'string') {
    return props.folder
  }
  if (props.folder && typeof props.folder === 'object') {
    return props.folder.folder || props.folder.foldername || ''
  }
  return ''
})

const isLoading = ref(false)
const errorMessage = ref('')
const downloadError = ref('')
const isDownloading = ref(false)
const files = ref([])
const subfolders = ref([])
const currentFolderId = ref(null)
const currentFolderName = ref('')
const breadcrumbStack = ref([])
let hasMounted = false

const canDownload = computed(
  () => !isLoading.value && !errorMessage.value && (subfolders.value.length > 0 || files.value.length > 0),
)

const humanFileSize = (value) => {
  if (!value && value !== 0) {
    return ''
  }
  const size = Number(value)
  if (Number.isNaN(size)) {
    return ''
  }
  if (size >= 1048576) {
    return `${(size / 1048576).toFixed(2)} MB`
  }
  if (size >= 1024) {
    return `${(size / 1024).toFixed(2)} KB`
  }
  return `${size} B`
}

const buildParams = ({ folderId = null, folderLabel = null }) => {
  const params = {}
  if (folderId) {
    params.folder_id = folderId
  }
  const labelCandidate = folderLabel ?? folderName.value
  if (!folderId && labelCandidate) {
    params.foldername = labelCandidate
  }
  return params
}

const loadFolder = async ({ folderId = null, folderLabel = null } = {}) => {
  const params = buildParams({ folderId, folderLabel })
  if (!params.folder_id && !params.foldername) {
    return null
  }
  isLoading.value = true
  errorMessage.value = ''
  downloadError.value = ''

  try {
    const resource = createResource({
      url: 'seminary.api.folder_upload.get_files_in_folder',
      params,
      auto: true,
    })
    const result = await resource.fetch()
    const entries = result?.entries || []
    subfolders.value = entries.filter((entry) => entry.is_folder)
    files.value = entries.filter((entry) => !entry.is_folder)
    currentFolderId.value = result?.folder_id || folderId || null
    currentFolderName.value = result?.folder_name || folderLabel || folderName.value || ''
    return {
      id: currentFolderId.value,
      label: currentFolderName.value,
    }
  } catch (error) {
    console.error('Error fetching folder contents:', error)
    errorMessage.value = error?.message || __('Unable to load folder contents.')
    subfolders.value = []
    files.value = []
    return null
  } finally {
    isLoading.value = false
  }
}

const openRootFolder = async () => {
  const root = await loadFolder({ folderLabel: folderName.value })
  if (root) {
    breadcrumbStack.value = [root]
  }
}

const openSubfolder = async (folder) => {
  if (!folder?.name) {
    return
  }
  const crumb = await loadFolder({ folderId: folder.name, folderLabel: folder.file_name })
  if (crumb) {
    breadcrumbStack.value = [...breadcrumbStack.value, crumb]
  }
}

const navigateToBreadcrumb = async (index) => {
  if (index < 0 || index >= breadcrumbStack.value.length) {
    return
  }
  const target = breadcrumbStack.value[index]
  const crumb = await loadFolder({ folderId: target.id, folderLabel: target.label })
  if (crumb) {
    breadcrumbStack.value = [...breadcrumbStack.value.slice(0, index), crumb]
  }
}

const downloadAll = async () => {
  if (isDownloading.value || !canDownload.value) {
    return
  }
  const params = new URLSearchParams()
  if (currentFolderId.value) {
    params.set('folder_id', currentFolderId.value)
  } else if (currentFolderName.value || folderName.value) {
    params.set('foldername', currentFolderName.value || folderName.value)
  } else {
    return
  }

  isDownloading.value = true
  downloadError.value = ''
  try {
    const response = await fetch(
      `/api/method/seminary.api.folder_upload.download_folder?${params.toString()}`,
      { credentials: 'include' },
    )
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error?.message || __('Unable to download folder.'))
    }
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${currentFolderName.value || folderName.value || 'folder'}.zip`
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  } catch (error) {
    console.error('Error downloading folder:', error)
    downloadError.value = error?.message || __('Unable to download folder.')
  } finally {
    isDownloading.value = false
  }
}

onMounted(async () => {
  hasMounted = true
  await openRootFolder()
})

watch(
  () => folderName.value,
  async (newValue, oldValue) => {
    if (!hasMounted) {
      return
    }
    const trimmed = (newValue || '').trim()
    const previous = (oldValue || '').trim()
    if (!trimmed || trimmed === previous) {
      return
    }
    await openRootFolder()
  },
)
</script>
