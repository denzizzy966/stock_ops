<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDocs } from '../stores/docs'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { listRecent } from '../lib/service'
import { DOC_TYPES, DOC_TYPE_LIST, docTypeCfg, serverTypeKey as typeKeyOf } from '../data/mock'
import AppBar from '../components/AppBar.vue'
import StatusBadge from '../components/StatusBadge.vue'
import FilterBar from '../components/FilterBar.vue'
import SearchSelect from '../components/SearchSelect.vue'
import SearchInput from '../components/SearchInput.vue'
import { fmtDateTime } from '../lib/util'

const docs = useDocs()
const app = useApp()
const master = useMaster()
const route = useRoute()
const router = useRouter()
const { t } = useI18n()

// Bisa dibuka dengan filter dari luar (drill-down Laporan): /docs?scope=server&type=SE_OUT&from=2026-11-01
const scope = ref(route.query.scope === 'server' ? 'server' : 'local') // 'local' | 'server'
const filterType = ref('ALL')
const statusTabs = ['ALL', 'pending', 'synced', 'error']
const filterStatus = ref(statusTabs.includes(route.query.status) ? route.query.status : 'ALL')
const activeCount = computed(() =>
  scope.value === 'local'
    ? (filterType.value !== 'ALL' ? 1 : 0) + (filterStatus.value !== 'ALL' ? 1 : 0)
    : (serverType.value !== 'ALL' ? 1 : 0) + (fromDate.value ? 1 : 0)
)

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
// Jenis yang dicakup list_recent (Penawaran tidak).
const SERVER_TYPES = ['MR', 'PR', 'SE_IN', 'SE_OUT', 'SE_TRANSFER', 'GRN', 'RET', 'OPN']
const PAGE = 20
const serverType = ref(SERVER_TYPES.includes(route.query.type) ? route.query.type : 'ALL')
const fromDate = ref(/^\d{4}-\d{2}-\d{2}$/.test(route.query.from || '') ? route.query.from : '')
const search = ref('')
const serverDocs = ref([])
const loadingServer = ref(false)
const loadingMore = ref(false)
const hasMore = ref(false)
let reqSeq = 0 // abaikan respons lama bila filter berganti saat request masih jalan

const serverOpts = (start) => ({
  limit: PAGE,
  start,
  doc_type: serverType.value !== 'ALL' ? serverType.value : undefined,
  txt: search.value.trim() || undefined,
  from_date: fromDate.value || undefined
})
async function loadServer() {
  const seq = ++reqSeq
  loadingServer.value = true
  try {
    const rows = await listRecent(listCompany.value, serverOpts(0))
    if (seq !== reqSeq) return
    serverDocs.value = rows
    hasMore.value = rows.length === PAGE
  } catch (e) {
    if (seq !== reqSeq) return
    app.notify(e && e.message ? e.message : String(e), 'error')
    serverDocs.value = []
    hasMore.value = false
  } finally {
    if (seq === reqSeq) loadingServer.value = false
  }
}
async function loadMore() {
  const seq = reqSeq
  loadingMore.value = true
  try {
    const rows = await listRecent(listCompany.value, serverOpts(serverDocs.value.length))
    if (seq !== reqSeq) return
    serverDocs.value = [...serverDocs.value, ...rows]
    hasMore.value = rows.length === PAGE
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  } finally {
    loadingMore.value = false
  }
}
watch(scope, (s) => {
  if (s === 'server' && !serverDocs.value.length) loadServer()
})
watch([serverType, fromDate], () => loadServer())
let searchTimer = null
watch(search, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadServer, 400)
})
onMounted(() => {
  if (scope.value === 'server') loadServer()
})

const docstatusClass = { 0: 's-pending', 1: 's-submitted', 2: 's-error' }
function wfLabel(state) {
  const map = { 'Pending Approval': 'approval.pending', Approved: 'approval.approved', Rejected: 'approval.rejected' }
  return map[state] ? t(map[state]) : state
}
function wfClass(state) {
  return { pending: state === 'Pending Approval', approved: state === 'Approved', rejected: state === 'Rejected' }
}
// Klik dokumen server → buka DI APLIKASI. Bila dokumen ini juga ada di perangkat (dibuat dari HP
// ini), buka detail lokal yang punya aksi (Submit / Ajukan / Buka Kembali); selain itu detail server.
// Hanya ikon Desk yang membuka tab baru.
function openDoc(d) {
  const local = docs.docs.find((x) => x.remoteName === d.name && x.doctype === d.doctype)
  if (local) router.push(`/doc/${local.localId}`)
  else router.push(`/sdoc/${encodeURIComponent(d.doctype)}/${encodeURIComponent(d.name)}`)
}
</script>

<template>
  <AppBar :title="t('list.title')" />
  <div class="content">
    <FilterBar :count="activeCount">
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
            <Icon :name="ty.icon" /> {{ ty.short }}
          </button>
        </div>
        <div class="chips" style="margin-top: 8px">
          <button v-for="s in statusTabs" :key="s" class="chip" :class="{ active: filterStatus === s }" @click="filterStatus = s">
            {{ s === 'ALL' ? t('common.all') : t('status.' + s) }}
          </button>
        </div>
      </template>
      <template v-else>
        <SearchInput v-model="search" :placeholder="t('list.searchNo')" style="margin-top: 10px" />
        <div class="chips" style="margin-top: 10px">
          <button class="chip" :class="{ active: serverType === 'ALL' }" @click="serverType = 'ALL'">{{ t('common.all') }}</button>
          <button v-for="k in SERVER_TYPES" :key="k" class="chip" :class="{ active: serverType === k }" @click="serverType = k">
            <Icon :name="docTypeCfg(k).icon" /> {{ docTypeCfg(k).short }}
          </button>
        </div>
        <div v-if="fromDate" class="chips" style="margin-top: 8px">
          <button class="chip active" @click="fromDate = ''">{{ t('list.since', { d: fromDate }) }} <Icon name="close" /></button>
        </div>
      </template>
    </FilterBar>

    <!-- ===== LOKAL ===== -->
    <template v-if="scope === 'local'">
      <div v-if="!localList.length" class="empty"><div class="big"><Icon name="list" /></div>{{ t('list.empty') }}</div>

      <div v-for="d in localList" :key="d.localId" class="list-item mt12" style="cursor: pointer" @click="router.push(`/doc/${d.localId}`)">
        <span class="lead-icon" :style="{ background: DOC_TYPES[d.type].color }"><Icon :name="DOC_TYPES[d.type].icon" /></span>
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
        ><Icon name="external" /></a>
      </div>
    </template>

    <!-- ===== SERVER ===== -->
    <template v-else>
      <div class="row between" style="margin: 2px 4px 8px; gap: 8px; align-items: center">
        <div v-if="!companyLocked && master.companyNames.length > 1" class="grow company-pick">
          <SearchSelect v-model="listCompany" :options="master.companyNames" :placeholder="t('form.company')" />
        </div>
        <span v-else class="tiny muted truncate">{{ listCompany }}</span>
        <button class="btn sm" :disabled="loadingServer" @click="loadServer"><Icon name="refresh" /></button>
      </div>
      <div v-if="loadingServer" class="empty"><div class="big"><Icon name="loading" spin /></div>…</div>
      <div v-else-if="!serverDocs.length" class="empty"><div class="big"><Icon name="list" /></div>{{ t('list.empty') }}</div>
      <div v-for="d in serverDocs" :key="d.name" class="list-item mt12" style="cursor: pointer" @click="openDoc(d)">
        <span class="lead-icon" :style="{ background: docTypeCfg(typeKeyOf(d)).color }"><Icon :name="docTypeCfg(typeKeyOf(d)).icon" /></span>
        <div class="grow" style="min-width: 0">
          <div class="row between">
            <div class="truncate" style="font-weight: 700">{{ d.name }}</div>
            <span class="badge-status" :class="docstatusClass[d.docstatus]">{{ t('status.' + d.docstatus) }}</span>
          </div>
          <div class="tiny muted truncate">
            {{ t('docType.' + typeKeyOf(d)) }} · {{ d.date }}
            <span v-if="d.workflow_state && d.workflow_state !== 'Approved'" class="wf-mini" :class="wfClass(d.workflow_state)">{{ wfLabel(d.workflow_state) }}</span>
          </div>
        </div>
        <a
          v-if="master.canOpenInDesk(d.doctype)"
          :href="master.deskUrl(d.doctype, d.name)"
          target="_blank"
          rel="noopener"
          class="desk-icon"
          :title="t('common.openInDesk')"
          @click.stop
        ><Icon name="external" /></a>
      </div>
      <button v-if="!loadingServer && hasMore" class="btn block mt12" :disabled="loadingMore" @click="loadMore">
        <Icon v-if="loadingMore" name="loading" spin /> {{ loadingMore ? t('common.loading') : t('list.loadMore') }}
      </button>
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
.company-pick { min-width: 0; }
.desk-icon {
  flex: none; align-self: center; text-decoration: none; font-size: 16px; line-height: 1;
  padding: 8px 9px; border: 1px solid var(--line); border-radius: 8px; margin-left: 4px;
}
</style>
