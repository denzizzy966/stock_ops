<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useI18n } from '../lib/i18n'
import { reportCounts } from '../lib/service'
import { docTypeCfg } from '../data/mock'
import AppBar from '../components/AppBar.vue'

const app = useApp()
const router = useRouter()
const { t } = useI18n()
const data = ref(null)
const loading = ref(false)

// Kelompok laporan → kunci jenis dokumen (sama dengan LIST_TYPES di server).
const GROUPS = [
  { title: 'report.mrGroup', keys: ['MR', 'PR'] },
  { title: 'report.seGroup', keys: ['SE_IN', 'SE_OUT', 'SE_TRANSFER'] },
  { title: 'report.receiptGroup', keys: ['GRN', 'RET', 'OPN'] }
]
const groups = computed(() => {
  const counts = (data.value && data.value.counts) || {}
  return GROUPS.map((g) => {
    const rows = g.keys
      .filter((k) => counts[k])
      .map((k) => ({ key: k, label: t('docType.' + k), color: docTypeCfg(k).color, icon: docTypeCfg(k).icon, count: counts[k] }))
    return { ...g, rows, total: rows.reduce((s, r) => s + r.count, 0) }
  }).filter((g) => g.rows.length)
})
const empty = computed(() => !loading.value && !groups.value.length)

// Drill-down: daftar dokumen server jenis ini sejak awal periode laporan.
function open(r) {
  router.push({ name: 'docs', query: { scope: 'server', type: r.key, from: data.value.period } })
}

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
        <div class="tiny muted">{{ t('report.period') }} · {{ t('report.tapHint') }}</div>
      </div>
      <button class="btn sm" :disabled="loading" @click="load"><Icon name="refresh" /></button>
    </div>

    <div v-if="loading" class="empty"><div class="big"><Icon name="loading" spin /></div>…</div>
    <div v-else-if="empty" class="empty"><div class="big"><Icon name="report" /></div>{{ t('report.none') }}</div>

    <template v-else>
      <template v-for="g in groups" :key="g.title">
        <div class="section-title">{{ t(g.title) }} · {{ g.total }}</div>
        <div class="card">
          <div v-for="r in g.rows" :key="r.key" class="item-line report-row" @click="open(r)">
            <span class="lead-icon" :style="{ background: r.color, width: '34px', height: '34px', fontSize: '17px' }"><Icon :name="r.icon" /></span>
            <div class="grow truncate">{{ r.label }}</div>
            <div style="font-weight: 800; font-size: 18px">{{ r.count }}</div>
            <span class="chev">›</span>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
.report-row { cursor: pointer; }
.chev { color: var(--muted); font-size: 20px; margin-left: 6px; }
</style>
