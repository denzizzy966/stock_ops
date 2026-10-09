<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDocs } from '../stores/docs'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { DOC_TYPES } from '../data/mock'
import { getPhotosByLocalId } from '../lib/idb'
import AppBar from '../components/AppBar.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { fmtDateTime } from '../lib/util'

const route = useRoute()
const router = useRouter()
const docs = useDocs()
const app = useApp()
const master = useMaster()
const { t } = useI18n()

const doc = computed(() => docs.byLocalId(route.params.localId))
const cfg = computed(() => (doc.value ? DOC_TYPES[doc.value.type] : null))
const totalQty = computed(() => (doc.value ? doc.value.items.reduce((s, i) => s + (Number(i.qty) || 0), 0) : 0))
// Dokumen sudah masuk alur workflow (Pending/Approved/Rejected) → tombol Submit tidak berlaku;
// requester tinggal menunggu keputusan approver (aksi ada di layar Persetujuan approver).
const inWorkflow = computed(() => {
  const w = doc.value && doc.value.workflowState
  return !!w && w !== 'Draft'
})
// Label tombol finalisasi: untuk MR Purchase = "Ajukan Persetujuan", lainnya = "Submit".
const submitLabel = computed(() => (doc.value && doc.value.type === 'PR' ? t('approval.submitForApproval') : t('detail.submit')))

// Foto dimuat dari IndexedDB sebagai object URL
const photoViews = ref([])
onMounted(async () => {
  if (!doc.value) return
  // Sinkronkan status terkini dari server (mis. sudah di-approve/reject oleh line manager).
  docs.refreshState(doc.value.localId)
  try {
    const recs = await getPhotosByLocalId(doc.value.localId)
    photoViews.value = recs.map((r) => ({ id: r.id, url: URL.createObjectURL(r.blob) }))
  } catch {
    photoViews.value = []
  }
})
onBeforeUnmount(() => photoViews.value.forEach((p) => URL.revokeObjectURL(p.url)))

function wfLabel(state) {
  const map = { 'Pending Approval': 'approval.pending', Approved: 'approval.approved', Rejected: 'approval.rejected' }
  return map[state] ? t(map[state]) : state
}
function wfClass(state) {
  return { pending: state === 'Pending Approval', approved: state === 'Approved', rejected: state === 'Rejected' }
}

function del() {
  if (confirm(t('detail.confirmDelete'))) {
    docs.remove(doc.value.localId)
    router.replace('/docs')
  }
}
function confirmCancel() {
  if (confirm(t('detail.confirmCancel'))) docs.cancel(doc.value.localId)
}
</script>

<template>
  <AppBar :title="doc ? (doc.remoteName || t('home.draftLocal')) : ''" back />
  <div class="content" v-if="doc">
    <div class="card">
      <div class="row" style="gap: 10px">
        <span class="lead-icon" :style="{ background: cfg.color }">{{ cfg.icon }}</span>
        <div class="grow">
          <div style="font-weight: 700">{{ t('docType.' + cfg.key) }}</div>
          <div class="tiny muted">{{ cfg.doctype }} · {{ cfg.meta }}</div>
        </div>
        <StatusBadge :status="doc.status" :submitted="doc.submitted" />
      </div>

      <div v-if="doc.workflowState" class="mt8">
        <span class="wf-chip" :class="wfClass(doc.workflowState)">{{ wfLabel(doc.workflowState) }}</span>
      </div>

      <div class="mt12" style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px">
        <div><div class="tiny muted">{{ t('form.company') }}</div><div class="small">{{ doc.company }}</div></div>
        <div><div class="tiny muted">{{ t('form.date') }}</div><div class="small">{{ doc.date }}</div></div>
        <div v-if="cfg.source"><div class="tiny muted">{{ t('form.sourceWh') }}</div><div class="small">{{ doc.sourceWarehouse }}</div></div>
        <div v-if="cfg.target"><div class="tiny muted">{{ t('form.targetWh') }}</div><div class="small">{{ doc.targetWarehouse }}</div></div>
        <div v-if="doc.purpose"><div class="tiny muted">{{ t('form.purpose') }}</div><div class="small">{{ doc.purpose }}</div></div>
        <div v-if="doc.supplier"><div class="tiny muted">{{ t('form.supplier') }}</div><div class="small">{{ doc.supplier }}</div></div>
        <div v-if="doc.customer"><div class="tiny muted">{{ t('form.customer') }}</div><div class="small">{{ doc.customer }}</div></div>
        <div v-if="doc.returnAgainst"><div class="tiny muted">{{ t('ret.receipt') }}</div><div class="small">{{ doc.returnAgainst }}</div></div>
        <div><div class="tiny muted">{{ t('detail.localId') }}</div><div class="tiny truncate">{{ doc.localId }}</div></div>
      </div>
      <div v-if="doc.remoteName" class="mt8 row between" style="align-items: center; gap: 8px">
        <div class="tiny muted" style="min-width: 0">ERPNext: <b>{{ doc.remoteName }}</b></div>
        <a
          v-if="master.canOpenInDesk(doc.doctype)"
          :href="master.deskUrl(doc.doctype, doc.remoteName)"
          target="_blank"
          rel="noopener"
          class="desk-link"
        >🖥️ {{ t('common.openInDesk') }}</a>
      </div>
      <div v-if="doc.remark" class="mt8 small">📝 {{ doc.remark }}</div>
      <div v-if="doc.geo" class="mt8 small">📍 <a :href="`https://maps.google.com/?q=${doc.geo}`" target="_blank" style="color: var(--brand)">{{ doc.geo }}</a></div>
    </div>

    <div class="card mt12">
      <div class="row between" style="margin-bottom: 6px">
        <div style="font-weight: 700">{{ t('common.items') }} ({{ doc.items.length }})</div>
        <div class="small muted">{{ t('common.total') }}: <b>{{ totalQty }}</b></div>
      </div>
      <div v-for="line in doc.items" :key="line.item_code" class="item-line">
        <img v-if="line.image" :src="line.image" class="thumb" alt="" />
        <span v-else class="thumb" style="display: grid; place-items: center; font-weight: 700; color: var(--muted)">
          {{ (line.item_name || '?').charAt(0).toUpperCase() }}
        </span>
        <div class="grow">
          <div class="truncate" style="font-weight: 600">{{ line.item_name }}</div>
          <div class="tiny muted">{{ line.item_code }}</div>
        </div>
        <div style="font-weight: 700">{{ line.qty }} <span class="tiny muted">{{ line.uom }}</span></div>
      </div>
    </div>

    <div v-if="photoViews.length" class="card mt12">
      <div style="font-weight: 700; margin-bottom: 10px">{{ t('form.photos') }} ({{ photoViews.length }})</div>
      <div class="photo-grid">
        <div v-for="p in photoViews" :key="p.id" class="ph"><img :src="p.url" alt="" /></div>
      </div>
    </div>

    <div class="card mt12 tiny muted">
      {{ t('detail.created') }}: {{ fmtDateTime(doc.createdAt) }}
      <span v-if="doc.error" style="color: var(--danger)"><br />{{ t('detail.error') }}: {{ doc.error }}</span>
    </div>

    <button
      v-if="doc.status !== 'synced'"
      class="btn brand block mt16"
      :disabled="!app.online || doc.status === 'syncing'"
      @click="docs.syncOne(doc.localId)"
    >
      {{ doc.status === 'syncing' ? t('detail.syncing') : app.online ? t('detail.syncNow') : t('detail.offlineCantSync') }}
    </button>

    <button
      v-if="doc.status === 'synced' && !doc.submitted && !doc.cancelled && !inWorkflow"
      class="btn ok block mt12"
      @click="docs.submit(doc.localId)"
    >
      {{ submitLabel }}
    </button>

    <div v-if="doc.workflowState === 'Pending Approval'" class="card mt12 tiny muted" style="text-align: center">
      {{ t('approval.waiting') }}
    </div>

    <!-- Ditolak: tampilkan alasan + jalan keluar (buka kembali → ajukan ulang). -->
    <template v-if="doc.workflowState === 'Rejected'">
      <div class="card mt12 reject-card">
        <div class="small" style="font-weight: 700">{{ t('approval.reason') }}</div>
        <div class="small mt8">{{ doc.approvalNote || t('approval.noReason') }}</div>
        <div class="tiny muted mt8">{{ t('approval.reopenHint') }}</div>
      </div>
      <button class="btn brand block mt12" :disabled="!app.online" @click="docs.reopen(doc.localId)">
        {{ t('approval.reopen') }}
      </button>
    </template>

    <button
      v-if="doc.submitted && master.canCancel"
      class="btn block mt12"
      @click="confirmCancel"
    >
      {{ t('detail.cancel') }}
    </button>

    <!-- Hapus hanya untuk dokumen yang belum masuk alur/submit di server (hapus lokal saja).
         Dokumen Menunggu Persetujuan / Submitted tidak boleh dihapus dari perangkat agar tidak
         menyisakan dokumen "yatim" di server. -->
    <button v-if="!inWorkflow && !doc.submitted" class="btn danger block mt12" @click="del">{{ t('common.delete') }}</button>
    <div style="height: 8px"></div>
  </div>

  <div class="content" v-else>
    <div class="empty"><div class="big">❓</div>{{ t('detail.notFound') }}</div>
  </div>
</template>

<style scoped>
.wf-chip {
  display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 700;
}
.wf-chip.pending { background: #fef3c7; color: #92400e; }
.wf-chip.approved { background: #dcfce7; color: #166534; }
.wf-chip.rejected { background: #fee2e2; color: #991b1b; }
.reject-card { border-left: 4px solid var(--danger); }
.desk-link {
  flex: none; font-size: 12px; font-weight: 700; color: var(--brand); text-decoration: none;
  padding: 5px 10px; border: 1px solid var(--brand); border-radius: 8px; white-space: nowrap;
}
</style>
