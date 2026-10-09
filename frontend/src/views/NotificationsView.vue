<script setup>
import { onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useI18n } from '../lib/i18n'
import AppBar from '../components/AppBar.vue'
import { fmtDateTime } from '../lib/util'

const app = useApp()
const router = useRouter()
const { t } = useI18n()

const items = computed(() => app.notifications)

onMounted(() => {
  // muat & tandai semua dibaca saat dibuka
  app.markNotificationsRead()
})

function stripHtml(s) {
  return (s || '').replace(/<[^>]*>/g, '').trim()
}
function open(n) {
  if ((n.document_type === 'Material Request' || n.document_type === 'Stock Entry') && n.document_name) {
    window.open(`/app/${n.document_type.toLowerCase().replace(/ /g, '-')}/${n.document_name}`, '_blank')
  }
}
</script>

<template>
  <AppBar :title="t('notif.title')" back :showNet="false" />
  <div class="content">
    <div v-if="items.length" class="row between" style="margin-bottom: 8px">
      <span class="small muted">{{ items.length }}</span>
      <button class="btn sm" @click="app.markNotificationsRead()"><Icon name="check" /> {{ t('notif.markAll') }}</button>
    </div>

    <div v-if="!items.length" class="empty">
      <div class="big"><Icon name="bell" /></div>
      {{ t('notif.empty') }}
    </div>

    <div
      v-for="n in items"
      :key="n.name"
      class="list-item"
      :style="{ cursor: 'pointer', opacity: n.read ? 0.7 : 1 }"
      @click="open(n)"
    >
      <span class="lead-icon" :style="{ background: n.read ? 'var(--muted)' : 'var(--brand)' }"><Icon name="bell" /></span>
      <div class="grow" style="min-width: 0">
        <div class="truncate" :style="{ fontWeight: n.read ? 500 : 800 }">{{ stripHtml(n.subject) }}</div>
        <div class="tiny muted truncate">{{ n.from_user }} · {{ fmtDateTime(n.creation) }}</div>
      </div>
    </div>
  </div>
</template>
