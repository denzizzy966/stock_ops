<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useDocs } from '../stores/docs'
import { useApp } from '../stores/app'
import { useI18n } from '../lib/i18n'
import { DOC_TYPES } from '../data/mock'
import AppBar from '../components/AppBar.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { fmtDateTime } from '../lib/util'

const docs = useDocs()
const app = useApp()
const router = useRouter()
const { t } = useI18n()

const outbox = computed(() => docs.outbox)
const synced = computed(() => docs.docs.filter((d) => d.status === 'synced'))
</script>

<template>
  <AppBar :title="t('sync.title')" back />
  <div class="content">
    <div class="card row between">
      <div>
        <span class="net-pill" :class="{ off: !app.online }" style="background: var(--brand-soft); color: var(--ink)">
          <span class="dot"></span>{{ app.online ? t('common.online') : t('common.offline') }}
        </span>
        <div class="tiny muted mt8">{{ t('sync.waiting', { n: outbox.length }) }} · {{ t('sync.syncedN', { n: synced.length }) }}</div>
      </div>
      <button class="btn brand" :disabled="!app.online || !outbox.length" @click="docs.syncAll()">{{ t('sync.syncAll') }}</button>
    </div>

    <div class="card mt12 row between">
      <div>
        <div style="font-weight: 700">{{ t('sync.autoSync') }}</div>
        <div class="tiny muted">{{ t('sync.autoSyncDesc') }}</div>
      </div>
      <label class="switch">
        <input type="checkbox" :checked="app.settings.autoSync" @change="app.saveSettings({ autoSync: $event.target.checked })" />
        <span class="slider"></span>
      </label>
    </div>

    <div class="section-title">{{ t('sync.outbox') }} ({{ outbox.length }})</div>
    <div v-if="!outbox.length" class="empty" style="padding: 30px">
      <div class="big"><Icon name="check-circle" /></div>
      {{ t('sync.allSynced') }}
    </div>
    <div
      v-for="d in outbox"
      :key="d.localId"
      class="list-item"
      style="cursor: pointer; margin-bottom: 10px"
      @click="router.push(`/doc/${d.localId}`)"
    >
      <span class="lead-icon" :style="{ background: DOC_TYPES[d.type].color }"><Icon :name="DOC_TYPES[d.type].icon" /></span>
      <div class="grow">
        <div class="truncate" style="font-weight: 600">{{ t('docType.' + d.type) }} · {{ d.items.length }} {{ t('common.items') }}</div>
        <div class="tiny muted">{{ fmtDateTime(d.createdAt) }}</div>
      </div>
      <StatusBadge :status="d.status" />
      <button
        class="btn sm brand"
        style="margin-left: 8px"
        :disabled="!app.online || d.status === 'syncing'"
        @click.stop="docs.syncOne(d.localId)"
      >
        {{ t('sync.sync') }}
      </button>
    </div>
  </div>
</template>
