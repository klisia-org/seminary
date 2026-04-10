<template>
  <button
    class="group flex w-full min-h-[44px] cursor-pointer items-center rounded-lg text-ink-gray-8 transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
    :class="[
  isCollapsed ? 'justify-center px-0 py-2' : 'justify-start px-3 py-2',
      isActive ? 'bg-surface-white shadow-sm ring-1 ring-outline-gray-1' : 'hover:bg-surface-gray-2'
    ]"
    @click="handleClick"
  >
    <Tooltip :text="label" placement="right">
      <span class="grid h-5 w-6 flex-shrink-0 place-items-center">
        <slot name="icon">
          <component :is="icon" class="h-4.5 w-4.5 text-ink-gray-7" />
        </slot>
      </span>
    </Tooltip>
    <span
      class="flex-shrink-0 text-base transition-all duration-200"
      :class="
        isCollapsed
          ? 'ml-0 w-0 overflow-hidden opacity-0'
          : 'ml-3 w-auto opacity-100'
      "
    >
      {{ label }}
    </span>
  </button>
</template>

<script setup>
import { Tooltip } from 'frappe-ui'
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const props = defineProps({
  icon: {
    type: Function,
  },
  label: {
    type: String,
    default: '',
  },
  to: {
    type: String,
    default: '',
  },
  isCollapsed: {
    type: Boolean,
    default: false,
  },

})

function handleClick() {
  router.push(props.to)
}

let isActive = computed(() => {
  return router.currentRoute.value.path === props.to
})

</script>