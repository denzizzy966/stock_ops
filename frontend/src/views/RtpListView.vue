<script setup>
// Request to Pay — daftar pengajuan: Perlu Tindakan (approver/pemroses bayar) · Pengajuan Saya · Semua.
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { listRtp } from '../lib/service'
import { fmtMoney, stateInfo } from '../lib/rtp'
import AppBar from '../components/AppBar.vue'
import SearchInput from '../components/SearchInput.vue'

const app = useApp()
const master = useMaster()
const router = useRouter()
const { t, locale } = useI18n()

const caps = computed(() => master.rtp)
const tabs = computed(() => {
  const out = []
  if ((caps.value.act_states || []).length) out.push({ key: 'todo', label: t('rtp.tabTodo') })
  if (caps.value.can_request) out.push({ key: 'mine', label: t('rtp.tabMine') })
  if (caps.value.can_view_all) out.push({ key: 'all', label: t('rtp.tabAll') })
  return out
})
// Tab terakhir diingat per perangkat (kenyamanan saja).
const saved = (() => {
  try {
    return localStorage.getItem('rtp.tab')
  } catch {
    return null
  }
})()
const scope = ref(tabs.value.some((x) => x.key === saved) ? saved : (tabs.value[0] || {}).key || 'mine')
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
    const r = await listRtp({ scope: scope.value, txt: q.value.trim() || undefined, start: append ? rows.value.length : 0, limit: 20 })
    if (my !== seq) return
    rows.value = append ? [...rows.value, ...(r.items || [])] : r.items || []
    hasMore.value = !!r.has_more
    if (master.caps && master.caps.rtp) master.caps.rtp.todo = r.todo || 0
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
    localStorage.setItem('rtp.tab', k)
  } catch {}
  load()
}
let timer = null
watch(q, () => {
  clearTimeout(timer)
  timer = setTimeout(() => load(), 350)
})
onMounted(() => load())
const money = (r) => fmtMoney(r.total_payment, r.currency, locale.value)
</script>

<template>
  <AppBar :title="t('rtp.title')" back />
  <div class="content">
    <div v-if="!app.online" class="card warn-card">{{ t('rtp.onlineOnly') }}</div>
    <template v-else>
      <div v-if="tabs.length > 1" class="seg" style="margin-bottom: 10px">
        <button v-for="tb in tabs" :key="tb.key" :class="{ active: scope === tb.key }" @click="setScope(tb.key)">
          {{ tb.label }}
          <span v-if="tb.key === 'todo' && caps.todo" class="tab-count">{{ caps.todo }}</span>
        </button>
      </div>
      <div class="row" style="gap: 8px; margin-bottom: 8px">
        <SearchInput v-model="q" :placeholder="t('rtp.search')" class="grow" />
        <button class="btn sm" :disabled="loading" @click="load()" :aria-label="t('common.loading')"><Icon name="refresh" :spin="loading" /></button>
      </div>
      <button v-if="caps.can_request" class="btn brand block" style="margin-bottom: 10px" @click="router.push('/rtp/new')">
        <Icon name="plus" /> {{ t('rtp.new') }}
      </button>

      <div v-if="loading && !rows.length" class="empty"><div class="big"><Icon name="loading" spin /></div>{{ t('common.loading') }}</div>
      <div v-else-if="!rows.length" class="empty">
        <div class="big"><Icon :name="scope === 'todo' ? 'check-circle' : 'inbox'" /></div>
        {{ scope === 'todo' ? t('rtp.noneTodo') : t('rtp.none') }}
      </div>

      <button v-for="r in rows" :key="r.name" type="button" class="list-item mt12 rtp-row" @click="router.push('/rtp/' + encodeURIComponent(r.name))">
        <span class="lead-icon" style="background: #0f766e"><Icon name="receipt" /></span>
        <div class="grow" style="min-width: 0; text-align: left">
          <div class="row between" style="gap: 6px">
            <span class="truncate" style="font-weight: 700">{{ r.name }}</span>
            <span class="badge-status" :class="stateInfo(r.workflow_state).cls">{{ t('rtp.state.' + stateInfo(r.workflow_state).key) }}</span>
          </div>
          <div class="small truncate" style="margin-top: 2px">{{ r.vendors || r.payment_purpose }}</div>
          <div class="tiny muted truncate">
            <span v-if="r.urgency === 'Urgent'" class="urgent-pill">{{ t('rtp.urgent') }}</span>
            {{ r.requester_name || r.requester }} · {{ r.payment_date }} · {{ r.invoice_count }} {{ t('rtp.invoices').toLowerCase() }}
          </div>
        </div>
        <div class="rtp-amt">{{ money(r) }}</div>
      </button>

      <button v-if="hasMore" class="btn block mt12" :disabled="loading" @click="load(true)">{{ t('rtp.loadMore') }}</button>
    </template>
  </div>
</template>

<style scoped>
.rtp-row { width: 100%; border: 0; cursor: pointer; font: inherit; color: inherit; }
.rtp-amt { font-weight: 800; font-size: 13px; white-space: nowrap; padding-left: 6px; }
.tab-count {
  display: inline-grid; place-items: center; min-width: 18px; height: 18px; padding: 0 5px; margin-left: 4px;
  border-radius: 9px; background: var(--danger, #dc2626); color: #fff; font-size: 11px;
}
.warn-card { color: var(--warn); font-weight: 600; }
</style>
