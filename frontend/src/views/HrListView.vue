<script setup>
// Menu HR — daftar Klaim Biaya / Kasbon: Perlu Tindakan (Expense Approver) · Pengajuan Saya.
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { listHr } from '../lib/service'
import { fmtMoney } from '../lib/rtp'
import { HR_KINDS, hrStatus } from '../lib/hr'
import AppBar from '../components/AppBar.vue'
import SearchInput from '../components/SearchInput.vue'

const app = useApp()
const master = useMaster()
const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()

const kind = computed(() => route.params.kind)
const cfg = computed(() => HR_KINDS[kind.value])
const caps = computed(() => master.hr[kind.value] || {})
const tabs = computed(() => {
  const out = []
  if (master.hr.can_approve) out.push({ key: 'todo', label: t('hr.tabTodo') })
  if (caps.value.can_request) out.push({ key: 'mine', label: t('hr.tabMine') })
  return out
})
const storeKey = computed(() => 'hr.tab.' + kind.value)
const readSaved = () => {
  try {
    return localStorage.getItem(storeKey.value)
  } catch {
    return null
  }
}
// Tab awal: pilihan terakhir; bila belum ada → "Perlu tindakan" kalau ada tugas, selain itu "Pengajuan saya".
function defaultScope() {
  const saved = readSaved()
  if (tabs.value.some((x) => x.key === saved)) return saved
  if (caps.value.todo && tabs.value.some((x) => x.key === 'todo')) return 'todo'
  return (tabs.value.find((x) => x.key === 'mine') || tabs.value[0] || {}).key || 'mine'
}
const scope = ref(defaultScope())
const q = ref('')
const rows = ref([])
const hasMore = ref(false)
const loading = ref(false)
let seq = 0

async function load(append = false) {
  if (!app.online) return
  const my = ++seq
  loading.value = true
  try {
    const r = await listHr(kind.value, { scope: scope.value, txt: q.value.trim() || undefined, start: append ? rows.value.length : 0, limit: 20 })
    if (my !== seq) return
    rows.value = append ? [...rows.value, ...(r.items || [])] : r.items || []
    hasMore.value = !!r.has_more
    if (master.hr[kind.value]) master.hr[kind.value].todo = r.todo || 0
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  } finally {
    if (my === seq) loading.value = false
  }
}
function setScope(k) {
  if (scope.value === k) return
  scope.value = k
  try {
    localStorage.setItem(storeKey.value, k)
  } catch {}
  load()
}
let timer = null
watch(q, () => {
  clearTimeout(timer)
  timer = setTimeout(() => load(), 350)
})
onMounted(() => load())
watch(kind, () => {
  rows.value = []
  scope.value = defaultScope()
  load()
})
const money = (r) => fmtMoney(r.amount, r.currency, locale.value)
const open = (r) => router.push(`/hr/${kind.value}/${encodeURIComponent(r.name)}`)
</script>

<template>
  <AppBar :title="t('hr.title.' + kind)" back />
  <div class="content">
    <div v-if="!app.online" class="card warn-card">{{ t('hr.onlineOnly') }}</div>
    <template v-else>
      <div v-if="tabs.length > 1" class="seg" style="margin-bottom: 10px">
        <button v-for="tb in tabs" :key="tb.key" :class="{ active: scope === tb.key }" @click="setScope(tb.key)">
          {{ tb.label }}
          <span v-if="tb.key === 'todo' && caps.todo" class="tab-count">{{ caps.todo }}</span>
        </button>
      </div>
      <div class="row" style="gap: 8px; margin-bottom: 8px">
        <SearchInput v-model="q" :placeholder="t('hr.search')" class="grow" />
        <button class="btn sm" :disabled="loading" @click="load()" :aria-label="t('common.loading')"><Icon name="refresh" :spin="loading" /></button>
      </div>
      <button v-if="caps.can_request" class="btn brand block" style="margin-bottom: 10px" @click="router.push(`/hr/${kind}/new`)">
        <Icon name="plus" /> {{ t('hr.new.' + kind) }}
      </button>

      <div v-if="loading && !rows.length" class="empty"><div class="big"><Icon name="loading" spin /></div>{{ t('common.loading') }}</div>
      <div v-else-if="!rows.length" class="empty">
        <div class="big"><Icon :name="scope === 'todo' ? 'check-circle' : 'inbox'" /></div>
        {{ scope === 'todo' ? t('hr.noneTodo') : t('hr.none') }}
      </div>

      <button v-for="r in rows" :key="r.name" type="button" class="list-item mt12 hr-row" @click="open(r)">
        <span class="lead-icon" :style="{ background: cfg.color }"><Icon :name="cfg.icon" /></span>
        <div class="grow" style="min-width: 0; text-align: left">
          <div style="font-weight: 700; white-space: nowrap">{{ r.name }}</div>
          <div class="small truncate" style="margin-top: 2px">{{ r.title || t('hr.menu.' + kind) }}</div>
          <div class="tiny muted truncate">{{ r.employee_name }} · {{ r.posting_date }}</div>
        </div>
        <div class="hr-right">
          <div class="hr-amt">{{ money(r) }}</div>
          <span class="badge-status" :class="hrStatus(r).cls">{{ t('hr.status.' + hrStatus(r).key) }}</span>
        </div>
      </button>

      <button v-if="hasMore" class="btn block mt12" :disabled="loading" @click="load(true)">{{ t('hr.loadMore') }}</button>
    </template>
  </div>
</template>

<style scoped>
.hr-row { width: 100%; border: 0; cursor: pointer; font: inherit; color: inherit; }
.hr-right { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; padding-left: 6px; flex: none; }
.hr-amt { font-weight: 800; font-size: 13px; white-space: nowrap; }
.tab-count {
  display: inline-grid; place-items: center; min-width: 18px; height: 18px; padding: 0 5px; margin-left: 4px;
  border-radius: 9px; background: var(--danger, #dc2626); color: #fff; font-size: 11px;
}
.warn-card { color: var(--warn); font-weight: 600; }
</style>
