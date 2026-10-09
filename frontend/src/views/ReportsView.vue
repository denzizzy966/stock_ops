<script setup>
import { ref, computed, onMounted } from 'vue'
import { useApp } from '../stores/app'
import { useI18n } from '../lib/i18n'
import { reportCounts } from '../lib/service'
import { DOC_TYPES } from '../data/mock'
import AppBar from '../components/AppBar.vue'

const app = useApp()
const { t } = useI18n()
const data = ref(null)
const loading = ref(false)

const MR_LABEL = { 'Material Transfer': 'MR', Purchase: 'PR' }
const SE_LABEL = { 'Material Receipt': 'SE_IN', 'Material Issue': 'SE_OUT', 'Material Transfer': 'SE_TRANSFER' }

function rows(obj, map) {
  if (!obj) return []
  return Object.keys(obj).map((k) => {
    const key = map[k]
    return { label: key ? t('docType.' + key) : k, color: key ? DOC_TYPES[key].color : '#888', icon: key ? DOC_TYPES[key].icon : 'list', count: obj[k] }
  })
}
const mrRows = computed(() => rows(data.value && data.value.mr, MR_LABEL))
const seRows = computed(() => rows(data.value && data.value.se, SE_LABEL))
const mrTotal = computed(() => mrRows.value.reduce((s, r) => s + r.count, 0))
const seTotal = computed(() => seRows.value.reduce((s, r) => s + r.count, 0))
const empty = computed(() => !loading.value && !mrRows.value.length && !seRows.value.length)

async function load() {
  loading.value = true
  try {
    data.value = await reportCounts(app.settings.company)
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<template>
  <AppBar :title="t('report.title')" back />
  <div class="content">
    <div class="card row between">
      <div>
        <div style="font-weight: 700">{{ app.settings.company }}</div>
        <div class="tiny muted">{{ t('report.period') }}</div>
      </div>
      <button class="btn sm" :disabled="loading" @click="load"><Icon name="refresh" /></button>
    </div>

    <div v-if="loading" class="empty"><div class="big"><Icon name="loading" spin /></div>…</div>
    <div v-else-if="empty" class="empty"><div class="big"><Icon name="report" /></div>{{ t('report.none') }}</div>

    <template v-else>
      <div class="section-title">{{ t('report.mrGroup') }} · {{ mrTotal }}</div>
      <div class="card" v-if="mrRows.length">
        <div v-for="(r, i) in mrRows" :key="i" class="item-line">
          <span class="lead-icon" :style="{ background: r.color, width: '34px', height: '34px', fontSize: '17px' }"><Icon :name="r.icon" /></span>
          <div class="grow truncate">{{ r.label }}</div>
          <div style="font-weight: 800; font-size: 18px">{{ r.count }}</div>
        </div>
      </div>

      <div class="section-title">{{ t('report.seGroup') }} · {{ seTotal }}</div>
      <div class="card" v-if="seRows.length">
        <div v-for="(r, i) in seRows" :key="i" class="item-line">
          <span class="lead-icon" :style="{ background: r.color, width: '34px', height: '34px', fontSize: '17px' }"><Icon :name="r.icon" /></span>
          <div class="grow truncate">{{ r.label }}</div>
          <div style="font-weight: 800; font-size: 18px">{{ r.count }}</div>
        </div>
      </div>
    </template>
  </div>
</template>
