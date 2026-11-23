<!--
  frappe-ui 0.1.261's FormControl (src/components/FormControl/FormControl.vue), fixed for
  decision 102 §9: an autocomplete's label pointed at an id nothing carried. A select,
  combobox or autocomplete gets the id only when there is a label, so one without keeps its
  own name. frappe-ui-overrides.js swaps it in for frappe-ui's own; keep it in step if
  frappe-ui is ever upgraded.
-->
<template>
  <div
    v-if="type != 'checkbox'"
    :class="['space-y-1.5', attrs.class]"
    :style="attrs.style"
  >
    <FormLabel
      v-if="label"
      :label="label"
      :size="size"
      :id="id"
      :required="required"
    />
    <Select
      v-if="type === 'select'"
      :id="label ? id : undefined"
      v-bind="{ ...controlAttrs, size, variant }"
    >
      <template #prefix v-if="$slots.prefix">
        <slot name="prefix" />
      </template>
    </Select>
    <Combobox
      v-else-if="type === 'combobox'"
      :id="label ? id : undefined"
      v-bind="{ ...controlAttrs, variant }"
    >
      <template #prefix v-if="$slots.prefix">
        <slot name="prefix" />
      </template>
    </Combobox>
    <Autocomplete
      v-else-if="type === 'autocomplete'"
      :id="label ? id : undefined"
      v-bind="{ ...controlAttrs }"
    >
      <template #prefix v-if="$slots.prefix">
        <slot name="prefix" />
      </template>
      <template #item-prefix="itemPrefixProps" v-if="$slots['item-prefix']">
        <slot name="item-prefix" v-bind="itemPrefixProps" />
      </template>
    </Autocomplete>
    <Textarea
      v-else-if="type === 'textarea'"
      :id="id"
      v-bind="{ ...controlAttrs, size, variant }"
    />
    <TextInput
      v-else
      :id="id"
      v-bind="{ ...controlAttrs, type, size, variant, required }"
    >
      <template #prefix v-if="$slots.prefix">
        <slot name="prefix" />
      </template>
      <template #suffix v-if="$slots.suffix">
        <slot name="suffix" />
      </template>
    </TextInput>
    <slot name="description">
      <p v-if="description" :class="descriptionClasses">{{ description }}</p>
    </slot>
  </div>
  <Checkbox
    v-else
    :id="id"
    v-bind="{ ...controlAttrs, label, size, class: attrs.class }"
  />
</template>
<script setup lang="ts">
import { useAttrs, computed, useId } from 'vue'
import {
  TextInput,
  Select,
  Textarea,
  Checkbox,
  Autocomplete,
  Combobox,
  FormLabel,
} from 'frappe-ui'

type TextInputTypes =
  | 'date'
  | 'datetime-local'
  | 'email'
  | 'file'
  | 'month'
  | 'number'
  | 'password'
  | 'search'
  | 'tel'
  | 'text'
  | 'time'
  | 'url'
  | 'week'
  | 'range'

interface FormControlProps {
  label?: string
  description?: string
  type?: TextInputTypes | 'textarea' | 'select' | 'checkbox' | 'autocomplete' | 'combobox'
  size?: 'sm' | 'md'
  variant?: 'subtle' | 'outline'
  required?: boolean
}

const id = useId()
const props = withDefaults(defineProps<FormControlProps>(), {
  type: 'text',
  size: 'sm',
  variant: 'subtle',
})

const attrs = useAttrs()
const controlAttrs = computed(() => {
  // pass everything except class and style
  let _attrs: typeof attrs = {}
  for (let key in attrs) {
    if (key !== 'class' && key !== 'style') {
      _attrs[key] = attrs[key]
    }
  }
  return _attrs
})

const descriptionClasses = computed(() => {
  return [
    {
      sm: 'text-xs',
      md: 'text-base',
    }[props.size],
    'text-ink-gray-5',
  ]
})
</script>
<script lang="ts">
export default {
  inheritAttrs: false,
}
</script>
