<template lang="">
    <div class="flex items-center justify-center h-[250px]">
      <p class="text-gray-500">{{message}}</p>
    </div>
  </template>
  <script setup>
  const props = defineProps({
    message: {
      type: String,
      default: __('No data found'),
    },
  })
  </script>