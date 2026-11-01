<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { getServerDoc, getAttachment, submitTransaction, applyWorkflowAction } from '../lib/service'
import { docTypeCfg, serverTypeKey } from '../data/mock'
import AppBar from '../components/AppBar.vue'
import { stripHtml, isNegativeStockError } from '../lib/util'

// Detail / pratinjau dokumen server DI APLIKASI — dari Daftar > Server, setelah Opname disimpan,
// dan setelah Permintaan Pembelian dari Stok Menipis dibuat. Bisa langsung Submit / Ajukan
// Persetujuan / Buka Kembali. Hanya tombol "Buka di Desk" yang membuka tab baru.
const route = useRoute()
const app = useApp()
const master = useMaster()
const { t } = useI18n()

const doctype = computed(() => route.params.doctype)
const name = computed(() => route.params.name)
const doc = ref(null)
const loading = ref(true)
const error = ref('')

const cfg = computed(() => (doc.value ? docTypeCfg(serverTypeKey(doc.value)) : null))
const isOpname = computed(() => doc.value && doc.value.doctype === 'Stock Reconciliation')
const isPurchaseMR = computed(() => doc.value && doc.value.doctype === 'Material Request' && doc.value.subtype === 'Purchase')
const canSubmit = computed(
  () => doc.value && doc.value.can_submit && (!doc.value.workflow_state || doc.value.workflow_state === 'Draft')
)
const submitLabel = computed(() => (isPurchaseMR.value ? t('approval.submitForApproval') : t('detail.submit')))
const canReopen = computed(
  () => doc.value && doc.value.workflow_state === 'Rejected' && doc.value.owner === (app.user && app.user.email)
)
// Approver: yang sudah ditetapkan, atau calon approver (leave approver) sebelum diajukan.
const approver = computed(() => doc.value && (doc.value.approver || doc.value.approver_preview))
const busy = ref(false)
async function run(fn, okMsg) {
  busy.value = true
  try {
    const res = await fn()
    app.notify(okMsg(res), 'success')
    await load()
  } catch (e) {
    // Pesan server bisa berisi HTML (mis. tautan item/gudang) → tampilkan sebagai teks.
    const raw = e && e.message ? e.message : String(e)
    const msg = stripHtml(raw)
    app.notify(isNegativeStockError(raw) ? `${t('toast.negativeStock')} — ${msg}` : msg, 'error')
  } finally {
    busy.value = false
  }
}
const submit = () =>
  run(
    () => submitTransaction(doc.value.doctype, doc.value.name),
    (r) => (r && r.workflow_state === 'Pending Approval' ? t('approval.submittedForApproval') + ' → ' + r.name : t('toast.submitted', { doc: r.name }))
  )
const reopen = () =>
  run(() => applyWorkflowAction(doc.value.doctype, doc.value.name, 'Reopen'), () => t('approval.reopened', { name: doc.value.name }))
const diffClass = (n) => (Number(n) > 0 ? 'diff-plus' : Number(n) < 0 ? 'diff-minus' : '')
const totalQty = computed(() => (doc.value ? doc.value.items.reduce((s, i) => s + (Number(i.qty) || 0), 0) : 0))
const docstatusClass = { 0: 's-pending', 1: 's-submitted', 2: 's-error' }
function wfLabel(state) {
  const map = { 'Pending Approval': 'approval.pending', Approved: 'approval.approved', Rejected: 'approval.rejected' }
  return map[state] ? t(map[state]) : state
}
function wfClass(state) {
  return { pending: state === 'Pending Approval', approved: state === 'Approved', rejected: state === 'Rejected' }
}

// Foto lampiran: diambil sebagai Blob lewat endpoint ber-auth (file private + token APK).
const photos = ref([]) // { name, file_name, url, failed }
const viewing = ref(null)
function releasePhotos() {
  photos.value.forEach((p) => p.url && URL.revokeObjectURL(p.url))
  photos.value = []
}
async function loadPhotos(files) {
  releasePhotos()
  photos.value = files.filter((f) => f.is_image).map((f) => ({ name: f.name, file_name: f.file_name, url: '', failed: false }))
  for (const p of photos.value) {
    try {
      p.url = URL.createObjectURL(await getAttachment(p.name))
    } catch {
      p.failed = true
    }
  }
}
const otherFiles = computed(() => (doc.value ? (doc.value.attachments || []).filter((f) => !f.is_image) : []))

async function load() {
  loading.value = true
  error.value = ''
  try {
    doc.value = await getServerDoc(doctype.value, name.value)
    loadPhotos(doc.value.attachments || [])
  } catch (e) {
    error.value = e && e.message ? e.message : String(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
onBeforeUnmount(releasePhotos)
</script>

<template>
  <AppBar :title="name" back />
  <div class="content">
    <div v-if="loading" class="empty"><div class="big"><Icon name="loading" spin /></div>{{ t('common.loading') }}</div>
    <div v-else-if="error" class="empty"><div class="big"><Icon name="lock" /></div>{{ error }}</div>
    <template v-else-if="doc">
      <div class="card">
        <div class="row" style="gap: 10px">
          <span class="lead-icon" :style="{ background: cfg.color }"><Icon :name="cfg.icon" /></span>
          <div class="grow" style="min-width: 0">
            <div style="font-weight: 700">{{ t('docType.' + cfg.key) }}</div>
            <div class="tiny muted truncate">{{ doc.doctype }}<span v-if="doc.subtype"> · {{ doc.subtype }}</span></div>
          </div>
          <span class="badge-status" :class="docstatusClass[doc.docstatus]">{{ t('status.' + doc.docstatus) }}</span>
        </div>

        <div v-if="doc.workflow_state && doc.workflow_state !== 'Draft'" class="mt8">
          <span class="wf-chip" :class="wfClass(doc.workflow_state)">{{ wfLabel(doc.workflow_state) }}</span>
        </div>

        <div class="mt12 detail-grid">
          <div><div class="tiny muted">{{ t('form.company') }}</div><div class="small">{{ doc.company }}</div></div>
          <div><div class="tiny muted">{{ t('form.date') }}</div><div class="small">{{ doc.date }}</div></div>
          <div v-if="doc.source_warehouse"><div class="tiny muted">{{ t('form.sourceWh') }}</div><div class="small">{{ doc.source_warehouse }}</div></div>
          <div v-if="doc.target_warehouse"><div class="tiny muted">{{ isOpname ? t('settings.warehouse') : t('form.targetWh') }}</div><div class="small">{{ doc.target_warehouse }}</div></div>
          <div v-if="doc.supplier"><div class="tiny muted">{{ t('form.supplier') }}</div><div class="small">{{ doc.supplier }}</div></div>
          <div v-if="doc.customer"><div class="tiny muted">{{ t('form.customer') }}</div><div class="small">{{ doc.customer }}</div></div>
          <div v-if="doc.purpose"><div class="tiny muted">{{ t('form.purpose') }}</div><div class="small">{{ doc.purpose }}</div></div>
          <div><div class="tiny muted">{{ t('approval.requester') }}</div><div class="small truncate">{{ doc.owner }}</div></div>
          <div v-if="approver || isPurchaseMR">
            <div class="tiny muted">{{ t('approval.approver') }}</div>
            <div class="small truncate">{{ approver || t('approval.noApprover') }}</div>
          </div>
        </div>
        <div v-if="doc.remarks" class="mt8 small"><Icon name="note" /> {{ doc.remarks }}</div>
        <a
          v-if="master.canOpenInDesk(doc.doctype)"
          :href="master.deskUrl(doc.doctype, doc.name)"
          target="_blank"
          rel="noopener"
          class="desk-link mt12"
        ><Icon name="external" /> {{ t('common.openInDesk') }}</a>
      </div>

      <div v-if="doc.workflow_state === 'Rejected'" class="card mt12 reject-card">
        <div class="small" style="font-weight: 700">{{ t('approval.reason') }}</div>
        <div class="small mt8">{{ doc.approval_note || t('approval.noReason') }}</div>
      </div>

      <div class="card mt12">
        <div class="row between" style="margin-bottom: 6px">
          <div style="font-weight: 700">{{ t('common.items') }} ({{ doc.items.length }})</div>
          <div class="small muted">{{ t('common.total') }}: <b>{{ totalQty }}</b></div>
        </div>
        <div v-for="(line, i) in doc.items" :key="i" class="item-line">
          <span class="thumb" style="display: grid; place-items: center; font-weight: 700; color: var(--muted)">
            {{ (line.item_name || line.item_code || '?').charAt(0).toUpperCase() }}
          </span>
          <div class="grow" style="min-width: 0">
            <div class="truncate" style="font-weight: 600">{{ line.item_name || line.item_code }}</div>
            <div class="tiny muted truncate">{{ line.item_code }}<span v-if="line.rejected_qty"> · {{ t('form.rejected') }} {{ line.rejected_qty }}</span></div>
          </div>
          <div v-if="isOpname" class="opn-qty">
            <div class="tiny muted">{{ t('opname.system') }} {{ line.current_qty }} → {{ t('opname.counted') }}</div>
            <div style="font-weight: 700">{{ line.qty }}</div>
            <div class="tiny" :class="diffClass(line.qty_difference)">{{ t('opname.diff') }} {{ Number(line.qty_difference) > 0 ? '+' : '' }}{{ line.qty_difference }}</div>
          </div>
          <div v-else style="font-weight: 700">{{ line.qty }} <span class="tiny muted">{{ line.uom }}</span></div>
        </div>
      </div>

      <div v-if="photos.length || otherFiles.length" class="card mt12">
        <div style="font-weight: 700; margin-bottom: 10px">{{ t('form.photos') }} ({{ photos.length }})</div>
        <div class="photo-grid">
          <div v-for="p in photos" :key="p.name" class="ph" @click="p.url && (viewing = p)">
            <img v-if="p.url" :src="p.url" :alt="p.file_name" />
            <span v-else class="ph-state"><Icon :name="p.failed ? 'warning' : 'loading'" :spin="!p.failed" /></span>
          </div>
        </div>
        <div v-for="f in otherFiles" :key="f.name" class="tiny muted mt8 truncate"><Icon name="note" /> {{ f.file_name }}</div>
      </div>

      <div v-if="doc.workflow_state === 'Pending Approval'" class="card mt12 tiny muted" style="text-align: center">
        {{ t('approval.waiting') }}
      </div>
      <div v-if="canSubmit && isPurchaseMR && !approver" class="card mt12 tiny warn-card">
        <Icon name="warning" /> {{ t('approval.noApproverHint') }}
      </div>
      <button v-if="canSubmit" class="btn ok block mt12" :disabled="busy || !app.online" @click="submit">
        {{ busy ? t('form.processing') : submitLabel }}
      </button>
      <button v-if="canReopen" class="btn brand block mt12" :disabled="busy || !app.online" @click="reopen">
        {{ t('approval.reopen') }}
      </button>
      <div style="height: 8px"></div>
    </template>
  </div>
  <div v-if="viewing" class="photo-viewer" @click="viewing = null">
    <img :src="viewing.url" :alt="viewing.file_name" />
    <button class="pv-close" :aria-label="t('common.back')"><Icon name="close" /></button>
  </div>
</template>

<style scoped>
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.detail-grid > div { min-width: 0; overflow-wrap: anywhere; }
.wf-chip { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
.wf-chip.pending { background: #fef3c7; color: #92400e; }
.wf-chip.approved { background: #dcfce7; color: #166534; }
.wf-chip.rejected { background: #fee2e2; color: #991b1b; }
.reject-card { border-left: 4px solid var(--danger); }
.warn-card { color: #92400e; background: #fef3c7; border: 1px solid #fcd34d; }
.opn-qty { text-align: right; flex: none; }
.diff-plus { color: #16a34a; font-weight: 700; }
.diff-minus { color: var(--danger); font-weight: 700; }
.ph-state { display: grid; place-items: center; width: 100%; height: 100%; color: var(--muted); font-size: 20px; }
.photo-grid .ph { cursor: zoom-in; }
.photo-viewer {
  position: fixed; inset: 0; z-index: 1000; background: rgba(0, 0, 0, 0.88);
  display: grid; place-items: center; padding: 16px;
}
.photo-viewer img { max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 8px; }
.pv-close {
  position: absolute; top: 14px; right: 14px; width: 38px; height: 38px; border-radius: 50%; border: 0;
  background: rgba(255, 255, 255, 0.18); color: #fff; font-size: 18px; display: grid; place-items: center;
}
.desk-link {
  display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 700; color: var(--brand);
  text-decoration: none; padding: 7px 12px; border: 1px solid var(--brand); border-radius: 8px;
}
</style>
