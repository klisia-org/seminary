import { h, createApp } from 'vue';
import FolderPlugin from '@/components/FolderPlugin.vue';
import FolderBlock from '@/components/FolderBlock.vue';
import { FolderOpen } from 'lucide-vue-next';
import translationPlugin from '../translation'
import router from '@/router'

const getCsrfToken = () => {
  if (typeof window === 'undefined') {
    return null
  }
  return (
    window.csrf_token ||
    window.frappe?.csrf_token ||
    document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
    null
  )
}

export class FolderTool {
  constructor({ data, api, readOnly }) {
    this.data = data;
    this.readOnly = readOnly
    this.api = api;
    this.wrapper = undefined;
    this.vueApp = null;
  }

  static get toolbox() {
    const app = createApp({
      render: () =>
        h(FolderOpen, { size: 18, strokeWidth: 1.5, color: 'black' }),
    });

    const div = document.createElement('div');
    app.mount(div);

    return {
      title: 'Folder',
      icon: div.innerHTML,
    };
  }
	static get isReadOnlySupported() {
		return true
	}

  render() {
    this.wrapper = document.createElement('div')
    if (this.data && this.data.folder) {
      this.renderFolder(this.data.folder)
    } else {
      this.renderFolderModal()
    }
    return this.wrapper
  }

  destroyApp() {
    if (this.vueApp) {
      this.vueApp.unmount()
      this.vueApp = null
    }
    if (this.wrapper) {
      this.wrapper.innerHTML = ''
    }
  }

  renderFolder(folderName) {
    if (this.readOnly) {
      this.destroyApp()
      this.vueApp = createApp(FolderBlock, {
        folder: folderName,
      })
      this.vueApp.use(translationPlugin)
      this.vueApp.use(router)
      this.vueApp.mount(this.wrapper)
      return
    }
    this.renderFolderModal(folderName)
  }

  renderFolderModal(initialFolder = null) {
    if (this.readOnly) {
      return
    }
    this.destroyApp()
    this.vueApp = createApp(FolderPlugin, {
      initialFolder,
      onAddition: (folder) => {
        if (!this.data) {
          this.data = {}
        }
        this.data.folder = folder
      },
    })
    this.vueApp.use(translationPlugin)
    this.vueApp.use(router)
    this.vueApp.mount(this.wrapper)
  }

    save(blockContent) {
      return {
        folder: this.data?.folder,
      }
    }

    destroy() {
      this.destroyApp()
    }

    async createCourseFolder(courseName, folderName) {
      const trimmedFolderName = folderName?.trim()
      if (!trimmedFolderName) {
        throw new Error('Folder name is required to create a course folder')
      }
      if (!courseName) {
        throw new Error('Course is required to create a course folder')
      }

      const csrfToken = getCsrfToken()
      if (!csrfToken) {
        throw new Error('CSRF token not found. Please refresh the page and try again.')
      }

      let responseData
      const response = await fetch('/api/resource/Course Folder', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          'X-Frappe-CSRF-Token': csrfToken,
        },
        credentials: 'include',
        body: JSON.stringify({
          course: courseName,
          foldername: trimmedFolderName,
        }),
      })
      try {
        responseData = await response.json()
      } catch (error) {
        responseData = null
      }

      if (!response.ok) {
        const serverMessage = responseData?.message || responseData?.exc || response.statusText
        throw new Error(serverMessage || 'Failed to create course folder')
      }

      const data = responseData?.data || responseData
      if (!this.data) {
        this.data = {}
      }
      this.data.folder = data?.foldername || trimmedFolderName
      return data
    }

    async createSubfolder({ parentFolderId, parentFolderName, subfolderName }) {
      const trimmedSubfolderName = subfolderName?.trim()
      if (!trimmedSubfolderName) {
        throw new Error('Sub-folder name is required')
      }

      if (!parentFolderId && !parentFolderName) {
        throw new Error('Parent folder information is required to create a sub-folder')
      }

      const csrfToken = getCsrfToken()
      if (!csrfToken) {
        throw new Error('CSRF token not found. Please refresh the page and try again.')
      }

      let responseData
      const response = await fetch('/api/method/seminary.api.folder_upload.create_subfolder', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          'X-Frappe-CSRF-Token': csrfToken,
        },
        credentials: 'include',
        body: JSON.stringify({
          parent_folder_id: parentFolderId,
          parent_foldername: parentFolderName,
          subfoldername: trimmedSubfolderName,
        }),
      })

      try {
        responseData = await response.json()
      } catch (error) {
        responseData = null
      }

      if (!response.ok) {
        const serverMessage = responseData?.message || responseData?.exc || response.statusText
        throw new Error(serverMessage || 'Failed to create sub-folder')
      }

      return responseData?.message || responseData?.data || responseData
    }
  }