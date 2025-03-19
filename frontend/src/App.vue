<template>
	<Layout>
		<router-view />
	</Layout>
	
	<Toasts />
	<Dialogs /> <!-- Ensure this line is present -->
</template>

<script setup>
import Sidebar from '@/components/AppSidebar.vue'
// import Navbar from '@/components/Navbar.vue';
// import { RouterView } from 'vue-router';
import { Toasts } from 'frappe-ui';
import { Dialogs } from '@/utils/dialogs'
import { usersStore } from '@/stores/user'
import { computed, onMounted, onUnmounted } from 'vue'
import { useScreenSize } from './utils/composables'
import DesktopLayout from './components/DesktopLayout.vue'


const screenSize = useScreenSize()
let { userResource } = usersStore()

const Layout = computed(() => {
  if (screenSize.width < 1024) {
    return DesktopLayout
  }
  return DesktopLayout
})


</script>