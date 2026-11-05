<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useApp } from './stores/app'
import TabBar from './components/TabBar.vue'

const route = useRoute()
const app = useApp()
const showTabs = computed(() => !!route.meta.tab && app.isLoggedIn)
</script>

<template>
  <div class="app-shell">
    <router-view v-slot="{ Component, route: r }">
      <!-- Form HR: klaim ↔ kasbon / baru ↔ ubah memakai komponen yang sama → paksa mount ulang per URL. -->
      <component :is="Component" :key="r.name === 'hr-new' || r.name === 'hr-edit' ? r.fullPath : undefined" />
    </router-view>

    <TabBar v-if="showTabs" />

    <transition name="fade">
      <div v-if="app.toast" class="toast" :class="app.toast.kind" @click="app.toast = null">
        {{ app.toast.message }}
      </div>
    </transition>
  </div>
</template>

<style>
.fade-enter-active, .fade-leave-active { transition: opacity .2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
