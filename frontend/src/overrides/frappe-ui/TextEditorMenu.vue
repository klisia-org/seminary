<!--
  frappe-ui 0.1.261's TextEditor toolbar (src/components/TextEditor/Menu.vue) with names
  on its buttons (decision 102 §9, WCAG 4.1.2): the grouped heading and list buttons show
  only an icon and had no name, and no button had type="button", so one inside a form
  submitted it. vite.config.js swaps this file in for frappe-ui's own; keep it in step
  with that file if frappe-ui is ever upgraded.
-->
<template>
  <div class="inline-flex bg-surface-white px-1 py-1">
    <div class="inline-flex items-center gap-1">
      <template v-for="button in buttons" :key="button.label">
        <div
          class="h-4 w-[2px] border-l"
          v-if="button.type === 'separator'"
        ></div>
        <div class="shrink-0" v-else-if="button.map">
          <Popover>
            <template #target="{ togglePopover }">
              <button
                type="button"
                class="rounded px-2 py-1 text-base font-medium text-ink-gray-8 transition-colors hover:bg-surface-gray-2"
                @click="togglePopover"
                :set="
                  activeBtn =
                    button.find((b) => b.isActive(editor)) || button[0]
                "
                :aria-label="activeBtn.label"
                :title="activeBtn.label"
                aria-haspopup="menu"
              >
                <component
                  v-if="activeBtn.icon"
                  :is="activeBtn.icon"
                  class="h-4 w-4"
                />
                <span v-else>
                  {{ activeBtn.label }}
                </span>
              </button>
            </template>
            <template #body="{ close }">
              <ul
                class="p-1.5 mt-2 rounded-lg bg-surface-modal shadow-2xl ring-1 ring-black ring-opacity-5 focus:outline-none"
              >
                <li
                  v-for="option in button"
                  v-show="option.isDisabled ? !option.isDisabled(editor) : true"
                >
                  <button
                    type="button"
                    class="w-full h-7 rounded px-2 text-base flex items-center gap-2 hover:bg-surface-gray-3"
                    @click="
                      () => {
                        onButtonClick(option)
                        close()
                      }
                    "
                  >
                    <component
                      v-if="option.icon"
                      :is="option.icon"
                      class="size-4 flex-shrink-0 text-ink-gray-6"
                    />
                    <span
                      v-if="option.label"
                      class="whitespace-nowrap text-ink-gray-7"
                      >{{ option.label }}</span
                    >
                  </button>
                </li>
              </ul>
            </template>
          </Popover>
        </div>
        <component v-else :is="button.component || 'div'" v-bind="{ editor }">
          <template v-slot="componentSlotProps">
            <button
              type="button"
              :aria-label="button.label"
              class="flex rounded p-1 text-ink-gray-8 transition-colors"
              :class="[
                button.isActive(editor) || componentSlotProps?.isActive
                  ? 'bg-surface-gray-3'
                  : 'hover:bg-surface-gray-2',
                button.class,
              ]"
              @click="
                componentSlotProps?.onClick
                  ? componentSlotProps.onClick(button)
                  : onButtonClick(button)
              "
              :title="button.label"
            >
              <component v-if="button.icon" :is="button.icon" class="h-4 w-4" />
              <span
                class="inline-block h-4 min-w-[1rem] text-sm leading-4"
                v-else
              >
                {{ button.text }}
              </span>
            </button>
          </template>
        </component>
      </template>
    </div>
  </div>
</template>
<script>
import Popover from 'frappe-ui/src/components/Popover/Popover.vue'

export default {
  name: 'TipTapMenu',
  props: ['buttons'],
  inject: ['editor'],
  components: {
    Popover,
  },
  methods: {
    onButtonClick(button) {
      button.action(this.editor)
    },
  },
}
</script>
