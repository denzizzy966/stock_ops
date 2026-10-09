<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useDocs } from '../stores/docs'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { listRecent } from '../lib/service'
import { DOC_TYPES, DOC_TYPE_LIST } from '../data/mock'
import AppBar from '../components/AppBar.vue'
import StatusBadge from '../components/StatusBadge.vue'
import FilterBar from '../components/FilterBar.vue'
import { fmtDateTime } from '../lib/util'

const docs = useDocs()
const app = useApp()
const master = useMaster()
const router = useRouter()
const { t } = useI18n()

const scope = ref('local') // 'local' | 'server'
const filterType = ref('ALL')
const filterStatus = ref('ALL')
const statusTabs = ['ALL', 'pending', 'synced', 'error']
const activeCount = computed(() => (filterType.value !== 'ALL' ? 1 : 0) + (filterStatus.value !== 'ALL' ? 1 : 0))

const localList = computed(() =>
  docs.sorted.filter((d) => {
    if (filterType.value !== 'ALL' && d.type !== filterType.value) return false
    if (filterStatus.value !== 'ALL' && d.status !== filterStatus.value) return false
    return true
  })
)

// ===== Server =====
// Perusahaan daftar server = perusahaan aktif perangkat (mengikuti Employee, lihat reconcileDefaults).
// User dengan beberapa perusahaan bisa menggantinya di sini; Company terkunci → hanya label.
const companyLocked = computed(() => !!(master.defaults && master.defaults.company_read_only))
const listCompany = computed({
  get: () => app.settings.company,
  set: (v) => {
    app.saveSettings({ company: v })
    loadServer()
  }
})
const serverDocs = ref([])
const loadingServer = ref(false)
async function loadServer() {
  loadingServer.value = true
  try {
    serverDocs.value = await listRecent(listCompany.value, 30)
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
    serverDocs.value = []
  } finally {
    loadingServer.value = false
  }
}
watch(scope, (s) => {
  if (s === 'server' && !serverDocs.value.length) loadServer()
})

// Petakan dokumen server → jenis app (untuk ikon/warna/label)
function typeKeyOf(d) {
  if (d.doctype === 'Material Request') return d.subtype === 'Purchase' ? 'PR' : 'MR'
  return { 'Material Receipt': 'SE_IN', 'Material Issue': 'SE_OUT', 'Material Transfer': 'SE_TRANSFER' }[d.subtype] || 'SE_TRANSFER'
}
const docstatusClass = { 0: 's-pending', 1: 's-submitted', 2: 's-error' }
function wfLabel(state) {
  const map = { 'Pending Approval': 'approval.pending', Approved: 'approval.approved', Rejected: 'approval.rejected' }
  return map[state] ? t(map[state]) : state
}
function wfClass(state) {
  return { pending: state === 'Pending Approval', approved: state === 'Approved', rejected: state === 'Rejected' }
}
// Buka dokumen server di Desk (tab baru) — hanya bila user punya akses/izin baca doctype.
function openInErp(d) {
  if (!master.canOpenInDesk(d.doctype)) return app.notify(t('common.noDeskPerm'), 'warn')
  window.open(master.deskUrl(d.doctype, d.name), '_blank', 'noopener')
}
</script>

<template>
  <AppBar :title="t('list.title')" />
  <div class="content">
    <FilterBar :collapsible="scope === 'local'" :count="activeCount">
      <template #bar>
        <div class="seg">
          <button :class="{ active: scope === 'local' }" @click="scope = 'local'">{{ t('list.local') }}</button>
          <button :class="{ active: scope === 'server' }" @click="scope = 'server'">{{ t('list.server') }}</button>
        </div>
      </template>
      <template v-if="scope === 'local'">
        <div class="chips" style="margin-top: 10px">
          <button class="chip" :class="{ active: filterType === 'ALL' }" @click="filterType = 'ALL'">{{ t('common.all') }}</button>
          <button v-for="ty in DOC_TYPE_LIST" :key="ty.key" class="chip" :class="{ active: filterType === ty.key }" @click="filterType = ty.key">
            {{ ty.icon }} {{ ty.short }}
          </button>
        </div>
        <div class="chips" style="margin-top: 8px">
          <button v-for="s in statusTabs" :key="s" class="chip" :class="{ active: filterStatus === s }" @click="filterStatus = s">
            {{ s === 'ALL' ? t('common.all') : t('status.' + s) }}
          </button>
        </div>
      </template>
    </FilterBar>

    <!-- ===== LOKAL ===== -->
    <template v-if="scope === 'local'">
      <div v-if="!localList.length" class="empty"><div class="big">📋</div>{{ t('list.empty') }}</div>

      <div v-for="d in localList" :key="d.localId" class="list-item mt12" style="cursor: pointer" @click="router.push(`/doc/${d.localId}`)">
        <span class="lead-icon" :style="{ background: DOC_TYPES[d.type].color }">{{ DOC_TYPES[d.type].icon }}</span>
        <div class="grow" style="min-width: 0">
          <div class="row between">
            <div class="truncate" style="font-weight: 700">{{ d.remoteName || t('home.draftLocal') }}</div>
            <StatusBadge :status="d.status" :submitted="d.submitted" />
          </div>
          <div class="tiny muted truncate">{{ t('docType.' + d.type) }} · {{ d.items.length }} {{ t('common.items') }} · {{ fmtDateTime(d.createdAt) }}</div>
          <div class="tiny muted truncate">{{ d.sourceWarehouse || '—' }} → {{ d.targetWarehouse || '—' }}</div>
        </div>
        <a
          v-if="d.remoteName && master.canOpenInDesk(DOC_TYPES[d.type].doctype)"
          :href="master.deskUrl(DOC_TYPES[d.type].doctype, d.remoteName)"
          target="_blank"
          rel="noopener"
          class="desk-icon"
          :title="t('common.openInDesk')"
          @click.stop
        >🖥️</a>
      </div>
    </template>

    <!-- ===== SERVER ===== -->
    <template v-else>
      <div class="row between" style="margin: 2px 4px 8px; gap: 8px; align-items: center">
        <select
          v-if="!companyLocked && master.companyNames.length > 1"
          v-model="listCompany"
          class="company-select"
          :aria-label="t('form.company')"
        >
          <option v-for="c in master.companyNames" :key="c" :value="c">{{ c }}</option>
        </select>
        <span v-else class="tiny muted truncate">{{ listCompany }}</span>
        <button class="btn sm" :disabled="loadingServer" @click="loadServer">🔄</button>
      </div>
      <div v-if="loadingServer" class="empty"><div class="big">⏳</div>…</div>
      <div v-else-if="!serverDocs.length" class="empty"><div class="big">📋</div>{{ t('list.empty') }}</div>
      <div v-for="d in serverDocs" :key="d.name" class="list-item mt12" style="cursor: pointer" @click="openInErp(d)">
        <span class="lead-icon" :style="{ background: DOC_TYPES[typeKeyOf(d)].color }">{{ DOC_TYPES[typeKeyOf(d)].icon }}</span>
        <div class="grow">
          <div class="row between">
            <div class="truncate" style="font-weight: 700">{{ d.name }}</div>
            <span class="badge-status" :class="docstatusClass[d.docstatus]">{{ t('status.' + d.docstatus) }}</span>
          </div>
          <div class="tiny muted truncate">
            {{ t('docType.' + typeKeyOf(d)) }} · {{ d.date }}
            <span v-if="d.workflow_state && d.workflow_state !== 'Approved'" class="wf-mini" :class="wfClass(d.workflow_state)">{{ wfLabel(d.workflow_state) }}</span>
          </div>
          <div v-if="master.canOpenInDesk(d.doctype)" class="tiny muted truncate">🖥️ {{ t('common.openInDesk') }} ↗</div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.wf-mini {
  display: inline-block; margin-left: 4px; padding: 1px 7px; border-radius: 999px; font-size: 10px; font-weight: 700;
}
.wf-mini.pending { background: #fef3c7; color: #92400e; }
.wf-mini.rejected { background: #fee2e2; color: #991b1b; }
.wf-mini.approved { background: #dcfce7; color: #166534; }
.company-select {
  flex: 1; min-width: 0; border: 1px solid var(--line); background: var(--input-bg); color: var(--ink);
  border-radius: 10px; padding: 8px 10px; font-size: 13px; font-weight: 600;
}
.desk-icon {
  flex: none; align-self: center; text-decoration: none; font-size: 16px; line-height: 1;
  padding: 8px 9px; border: 1px solid var(--line); border-radius: 8px; margin-left: 4px;
}
</style>
