<!--
  frappe-ui 0.1.261's TabButtons (src/components/TabButtons/TabButtons.vue) without a
  button inside each radio (WCAG 4.1.2, axe nested-interactive): frappe-ui wraps a focusable
  Button in each focusable RadioGroupOption, so a screen reader meets two controls for one
  choice. Here the option itself is the control and is drawn like the small subtle Button.
  frappe-ui-overrides.js swaps it in for frappe-ui's own; keep it in step if frappe-ui is ever
  upgraded.
-->
<template>
  <RadioGroup v-model="value">
    <div
      class="flex space-x-0.5 rounded-md bg-surface-gray-2 h-7 items-center px-[1px] text-sm"
    >
      <RadioGroupOption
        as="div"
        v-for="button in buttons"
        :key="button.label"
        :disabled="button.disabled"
        :value="button.value ?? button.label"
        :aria-label="button.hideLabel ? button.label : undefined"
        v-slot="{ active, checked }"
        class="rounded"
        @click="button.onClick && button.onClick($event)"
      >
        <div
          class="inline-flex h-6.5 items-center justify-center gap-2 rounded px-2 text-base transition-colors"
          :class="[
            active ? 'ring-outline-gray-2 focus-visible:ring' : '',
            button.disabled
              ? 'cursor-not-allowed text-ink-gray-4'
              : checked
                ? 'cursor-pointer bg-surface-white text-ink-gray-8 shadow'
                : 'cursor-pointer text-ink-gray-5 hover:bg-surface-gray-3',
          ]"
        >
          <FeatherIcon
            v-if="button.icon && typeof button.icon === 'string'"
            :name="button.icon"
            class="h-4 w-4"
            aria-hidden="true"
          />
          <component v-else-if="button.icon" :is="button.icon" class="h-4 w-4" aria-hidden="true" />
          <RadioGroupLabel
            as="span"
            class="flex h-4 items-center"
            v-show="button.label && !button.hideLabel"
            >{{ button.label }}</RadioGroupLabel
          >
        </div>
      </RadioGroupOption>
    </div>
  </RadioGroup>
</template>
<script>
import { RadioGroup, RadioGroupLabel, RadioGroupOption } from '@headlessui/vue'
import FeatherIcon from 'frappe-ui/src/components/FeatherIcon.vue'

export default {
  name: 'TabButtons',
  props: {
    buttons: {
      type: Array,
      required: true,
    },
    modelValue: {
      type: [String, Boolean, Number],
    },
  },
  emits: ['update:modelValue'],
  components: {
    FeatherIcon,
    RadioGroup,
    RadioGroupOption,
    RadioGroupLabel,
  },
  computed: {
    value: {
      get() {
        return this.modelValue
      },
      set(value) {
        this.$emit('update:modelValue', value)
      },
    },
  },
}
</script>
