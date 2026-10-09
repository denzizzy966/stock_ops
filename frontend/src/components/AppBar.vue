<script setup>
import { useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useI18n } from '../lib/i18n'

defineProps({
  title: { type: String, default: '' },
  back: { type: Boolean, default: false },
  logo: { type: Boolean, default: false },
  showNet: { type: Boolean, default: true },
  bell: { type: Boolean, default: false },
  bellCount: { type: Number, default: 0 }
})
const router = useRouter()
const app = useApp()
const { t } = useI18n()
function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/')
}
</script>

<template>
  <header class="appbar">
    <button v-if="back" class="back" @click="goBack" :aria-label="t('common.back')">‹</button>
    <div class="title">
      <img v-if="logo" src="/rmi-logo.png" class="logo" alt="RMI" />
      <span v-else>{{ title }}</span>
    </div>

    <button v-if="bell" class="bell-btn" @click="router.push('/notifications')" aria-label="notifications">
      <Icon name="bell" />
      <span v-if="bellCount" class="bell-badge">{{ bellCount > 99 ? '99+' : bellCount }}</span>
    </button>

    <button
      v-if="showNet"
      class="net-pill"
      :class="{ off: !app.online }"
      @click="app.setForceOffline(!app.forceOffline)"
    >
      <span class="dot"></span>{{ app.online ? t('common.online') : t('common.offline') }}
    </button>
  </header>
</template>
