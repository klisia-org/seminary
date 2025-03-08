<!-- filepath: /home/drmrmelo/cacs/apps/seminary/frontend/src/components/Breadcrumbs.vue -->
<template>
    <nav aria-label="breadcrumb">
      <ol class="breadcrumb">
        <li v-for="(item, index) in items" :key="index" class="breadcrumb-item">
          <router-link :to="item.route">{{ item.label }}</router-link>
        </li>
      </ol>
    </nav>
  </template>
  
  <script setup>
  import { defineProps } from 'vue'
  
  const props = defineProps({
    items: {
      type: Array,
      required: true,
    },
  })
  </script>
  
  <style scoped>
  .breadcrumb {
    display: flex;
    flex-wrap: wrap;
    padding: 0.75rem 1rem;
    margin-bottom: 1rem;
    list-style: none;
    background-color: #e9ecef;
    border-radius: 0.25rem;
  }
  
  .breadcrumb-item + .breadcrumb-item::before {
    content: ">";
    padding: 0 0.5rem;
    color: #6c757d;
  }
  </style>