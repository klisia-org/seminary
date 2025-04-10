import { h, createApp } from 'vue';
import FolderPlugin from '@/components/FolderPlugin.vue';
import FolderBlock from '@/components/FolderBlock.vue';
import { FolderOpen } from 'lucide-vue-next';
import translationPlugin from '../translation'
import router from '@/router'

export class FolderTool {
  constructor({ data, api, readOnly }) {
    this.data = data;
    this.readOnly = readOnly
    this.api = api;
    this.wrapper = undefined;
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
        this.renderFolder(this.data)
      } else {
        this.renderFolderModal()
      }
      return this.wrapper
    }
  
    renderFolder(folder) {
      if (this.readOnly) {
        const app = createApp(FolderBlock, {
          folder: folder,
        })
        app.use(translationPlugin)
        app.use(router)
        app.mount(this.wrapper)
        return
      }
      this.wrapper.innerHTML = `<div class='border rounded-md p-10 text-center bg-surface-menu-bar mb-2'>
              <span class="font-medium">
                  Folder: ${folder}
              </span>
          </div>`
      return
    }
  
    renderFolderModal() {
      if (this.readOnly) {
        return
      }
      const app = createApp(FolderPlugin, {
        
        onAddition: (folder) => {
          this.data.folder = folder
          this.renderFolder(folder)
        },
      })
      app.use(translationPlugin)
      app.use(router); // Explicitly provide the router
      app.mount(this.wrapper)
    }
  
    save(blockContent) {
      return {
        folder: this.data.folder,
      }
    }
  }