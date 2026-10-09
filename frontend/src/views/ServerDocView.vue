<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { getServerDoc } from '../lib/service'
import { DOC_TYPES, serverTypeKey } from '../data/mock'
import AppBar from '../components/AppBar.vue'

// Detail dokumen server (dari Daftar > Server) DITAMPILKAN DI APLIKASI.
// Hanya tombol "Buka di Desk" yang membuka tab baru.
const route = useRoute()
const app = useApp()
const master = useMaster()
const { t } = useI18n()

const doctype = computed(() => route.params.doctype)
const name = computed(() => route.params.name)
const doc = ref(null)
const loading = ref(true)
const error = ref('')

const cfg = computed(() => (doc.value ? DOC_TYPES[serverTypeKey(doc.value)] : null))
const totalQty = computed(() => (doc.value ? doc.value.items.reduce((s, i) => s + (Number(i.qty) || 0), 0) : 0))
const docstatusClass = { 0: 's-pending', 1: 's-submitted', 2: 's-error' }
function wfLabel(state) {
  const map = { 'Pending Approval': 'approval.pending', Approved: 'approval.approved', Rejected: 'approval.rejected' }
  return map[state] ? t(map[state]) : state
}
function wfClass(state) {
  return { pending: state === 'Pending Approval', approved: state === 'Approved', rejected: state === 'Rejected' }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    doc.value = await getServerDoc(doctype.value, name.value)
  } catch (e) {
    error.value = e && e.message ? e.message : String(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
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

        <div v-if="doc.workflow_state" class="mt8">
          <span class="wf-chip" :class="wfClass(doc.workflow_state)">{{ wfLabel(doc.workflow_state) }}</span>
        </div>

        <div class="mt12 detail-grid">
          <div><div class="tiny muted">{{ t('form.company') }}</div><div class="small">{{ doc.company }}</div></div>
          <div><div class="tiny muted">{{ t('form.date') }}</div><div class="small">{{ doc.date }}</div></div>
          <div v-if="doc.source_warehouse"><div class="tiny muted">{{ t('form.sourceWh') }}</div><div class="small">{{ doc.source_warehouse }}</div></div>
          <div v-if="doc.target_warehouse"><div class="tiny muted">{{ t('form.targetWh') }}</div><div class="small">{{ doc.target_warehouse }}</div></div>
          <div v-if="doc.supplier"><div class="tiny muted">{{ t('form.supplier') }}</div><div class="small">{{ doc.supplier }}</div></div>
          <div v-if="doc.customer"><div class="tiny muted">{{ t('form.customer') }}</div><div class="small">{{ doc.customer }}</div></div>
          <div v-if="doc.purpose"><div class="tiny muted">{{ t('form.purpose') }}</div><div class="small">{{ doc.purpose }}</div></div>
          <div><div class="tiny muted">{{ t('approval.requester') }}</div><div class="small truncate">{{ doc.owner }}</div></div>
          <div v-if="doc.approver"><div class="tiny muted">{{ t('approval.approver') }}</div><div class="small truncate">{{ doc.approver }}</div></div>
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
          <div style="font-weight: 700">{{ line.qty }} <span class="tiny muted">{{ line.uom }}</span></div>
        </div>
      </div>
      <div style="height: 8px"></div>
    </template>
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
.desk-link {
  display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 700; color: var(--brand);
  text-decoration: none; padding: 7px 12px; border: 1px solid var(--brand); border-radius: 8px;
}
</style>
