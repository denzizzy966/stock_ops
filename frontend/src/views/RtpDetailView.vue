<script setup>
// Request to Pay — detail pengajuan + aksi Workflow (Setujui / Tolak / Tandai Dibayar / Buka Kembali).
// Tombol aksi datang dari server (role + kondisi + company), jadi tampilan selalu sesuai hak user.
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { getRtp, applyRtpAction, getRtpFile } from '../lib/service'
import { fmtMoney, stateInfo, RTP_ACTIONS, RTP_STATES } from '../lib/rtp'
import { fmtDateTime, stripHtml } from '../lib/util'
import AppBar from '../components/AppBar.vue'
import Sheet from '../components/Sheet.vue'

const app = useApp()
const master = useMaster()
const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()

const name = computed(() => route.params.name)
const data = ref(null)
const loading = ref(true)
const busy = ref(false)
const d = computed(() => (data.value ? data.value.doc : {}))
const money = (v) => fmtMoney(v, d.value.currency, locale.value)
const st = computed(() => stateInfo(d.value.workflow_state))

async function load() {
  loading.value = true
  try {
    data.value = await getRtp(name.value)
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  } finally {
    loading.value = false
  }
}
onMounted(load)

// ── Aksi: semua lewat sheet konfirmasi (tanpa dialog browser) ──
const sheet = ref(null) // { action }
const note = ref('')
const payRef = ref('')
function startAction(action) {
  note.value = ''
  payRef.value = ''
  if (action === 'Reopen' || action === 'Submit') return run(action)
  sheet.value = { action }
}
const sheetTitle = computed(() => {
  const a = sheet.value && sheet.value.action
  return a === 'Reject' ? t('rtp.rejectTitle') : a === 'Mark as Paid' ? t('rtp.paidTitle') : t('rtp.approveTitle')
})
async function run(action) {
  if (action === 'Reject' && !note.value.trim()) return app.notify(t('rtp.rejectReason'), 'error')
  busy.value = true
  try {
    const r = await applyRtpAction(name.value, action, note.value.trim() || undefined, payRef.value.trim() || undefined)
    const label = t('rtp.state.' + stateInfo(r.workflow_state).key)
    app.notify(t('rtp.applied', { name: r.name, state: label }), 'success')
    sheet.value = null
    if (action === 'Reopen') return router.replace('/rtp/' + encodeURIComponent(r.name) + '/edit')
    await load()
    if (master.caps && master.caps.rtp && action !== 'Submit') master.caps.rtp.todo = Math.max(0, (master.caps.rtp.todo || 1) - 1)
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  } finally {
    busy.value = false
  }
}
const actionLabel = (a) => (RTP_ACTIONS[a] ? t('rtp.action.' + RTP_ACTIONS[a].key) : a)
// Status Purchase Invoice (dibuat Finance di Desk) per baris invoice.
const piPaid = (inv) => inv.pi_status !== 'Draft' && Number(inv.pi_outstanding) <= 0.01
const piCls = (inv) => (inv.pi_status === 'Draft' ? 'draft' : piPaid(inv) ? 'paid' : '')
const piLabel = (inv) => (inv.pi_status === 'Draft' ? t('rtp.piDraft') : piPaid(inv) ? t('rtp.piPaid') : t('rtp.piUnpaid'))
const actionCls = (a) => (RTP_ACTIONS[a] ? RTP_ACTIONS[a].cls : '')

// ── Pratinjau file invoice (lewat endpoint ber-izin; APK tak bisa memakai URL /private langsung) ──
const preview = ref(null) // { url, isImage, name }
async function openFile(inv) {
  try {
    const blob = await getRtpFile(name.value, inv.invoice_file)
    const isImage = (blob.type || '').startsWith('image/')
    const url = URL.createObjectURL(blob)
    if (!isImage) {
      window.open(url, '_blank')
      setTimeout(() => URL.revokeObjectURL(url), 60000)
      return
    }
    preview.value = { url, isImage, name: inv.invoice_file.split('/').pop() }
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  }
}
function closePreview() {
  if (preview.value) URL.revokeObjectURL(preview.value.url)
  preview.value = null
}
onBeforeUnmount(closePreview)

const history = computed(() =>
  (data.value?.history || []).map((h) => {
    const raw = stripHtml(h.content)
    return { ...h, text: h.comment_type === 'Workflow' && RTP_STATES[raw] ? t('rtp.state.' + RTP_STATES[raw].key) : raw }
  })
)
</script>

<template>
  <AppBar :title="name" back />
  <div class="content">
    <div v-if="loading && !data" class="empty"><div class="big"><Icon name="loading" spin /></div>{{ t('common.loading') }}</div>
    <template v-else-if="data">
      <div class="card">
        <div class="row between" style="gap: 8px">
          <span class="badge-status" :class="st.cls">{{ t('rtp.state.' + st.key) }}</span>
          <span v-if="d.urgency === 'Urgent'" class="urgent-pill">{{ t('rtp.urgent') }}</span>
        </div>
        <div class="grand-amt">{{ money(d.total_payment) }}</div>
        <div class="small">{{ d.payment_purpose }}</div>
        <div v-if="d.purpose_detail" class="tiny muted">{{ d.purpose_detail }}</div>
        <div class="kv mt12">
          <div><span>{{ t('rtp.requester') }}</span><b>{{ d.requester_name || d.requester }}</b></div>
          <div><span>{{ t('rtp.paymentDate') }}</span><b>{{ d.payment_date }}</b></div>
          <div><span>{{ t('rtp.company') }}</span><b>{{ d.company }}</b></div>
          <div><span>{{ t('rtp.department') }}</span><b>{{ d.department }}</b></div>
          <div><span>{{ t('rtp.businessUnit') }}</span><b>{{ d.business_unit }}</b></div>
          <div v-if="d.position"><span>{{ t('rtp.position') }}</span><b>{{ d.position }}</b></div>
        </div>
        <div v-if="d.requires_hod" class="tiny muted mt8">{{ t('rtp.requiresHod') }}</div>
        <div v-if="d.approval_note" class="note-box mt12">
          <div class="tiny muted">{{ t('rtp.approvalNote') }}</div>
          <div class="small">{{ d.approval_note }}</div>
        </div>
        <div v-if="d.workflow_state === 'Paid'" class="kv mt12">
          <div><span>{{ t('rtp.paidOn') }}</span><b>{{ d.paid_on || '—' }}</b></div>
          <div><span>{{ t('rtp.paymentRef') }}</span><b>{{ d.payment_reference || '—' }}</b></div>
        </div>
      </div>

      <div class="section-title">{{ t('rtp.invoices') }} ({{ d.invoices.length }})</div>
      <div v-for="inv in d.invoices" :key="inv.name" class="card mt12">
        <div class="row between" style="gap: 8px">
          <div style="min-width: 0">
            <div class="truncate" style="font-weight: 700">{{ inv.vendor_name }}</div>
            <div class="tiny muted truncate">{{ inv.invoice_no || '—' }}<template v-if="inv.supplier"> · {{ inv.supplier }}</template></div>
          </div>
          <button v-if="inv.invoice_file" class="btn sm" @click="openFile(inv)"><Icon name="eye" /> {{ t('rtp.viewFile') }}</button>
        </div>
        <div class="kv mt8">
          <div><span>{{ t('rtp.amount') }}</span><b>{{ money(inv.amount) }}</b></div>
          <template v-if="inv.tax_withheld">
            <div><span>{{ t('rtp.taxAmount') }} ({{ inv.tax_type ? inv.tax_type + ' · ' : '' }}{{ inv.tax_rate }}%)</span><b>− {{ money(inv.tax_amount) }}</b></div>
            <div><span>Tax ID</span><b>{{ inv.tax_id }}</b></div>
          </template>
          <div><span>{{ t('rtp.net') }}</span><b>{{ money(inv.net_amount) }}</b></div>
        </div>
        <div v-if="inv.notes" class="tiny muted mt8">{{ inv.notes }}</div>
        <div v-if="inv.purchase_invoice" class="pi-line mt8">
          <span class="tiny muted">{{ t('rtp.pi') }}</span>
          <b class="small">{{ inv.purchase_invoice }}</b>
          <span class="pi-badge" :class="piCls(inv)">{{ piLabel(inv) }}</span>
        </div>
      </div>
      <div v-if="d.invoices.some((i) => i.purchase_invoice) && d.workflow_state === 'Approved'" class="tiny muted mt8">{{ t('rtp.piNote') }}</div>

      <div class="card mt12 totals">
        <div class="row between"><span>{{ t('rtp.totalInvoice') }}</span><b>{{ money(d.total_amount) }}</b></div>
        <div class="row between"><span>{{ t('rtp.totalTax') }}</span><b>− {{ money(d.total_tax) }}</b></div>
        <div class="row between grand"><span>{{ t('rtp.totalPayment') }}</span><b>{{ money(d.total_payment) }}</b></div>
      </div>

      <div v-if="history.length" class="section-title">{{ t('rtp.history') }}</div>
      <div v-if="history.length" class="card">
        <div v-for="(h, i) in history" :key="i" class="hist">
          <div class="small"><b>{{ h.owner_name }}</b> · {{ h.text }}</div>
          <div class="tiny muted">{{ fmtDateTime(h.creation) }}</div>
        </div>
      </div>

      <div class="actions">
        <button v-if="data.can_edit" class="btn grow" :disabled="busy" @click="router.push('/rtp/' + encodeURIComponent(name) + '/edit')">
          {{ t('rtp.edit') }}
        </button>
        <button v-for="a in data.actions" :key="a" class="btn grow" :class="actionCls(a)" :disabled="busy" @click="startAction(a)">
          <Icon v-if="busy" name="loading" spin /> {{ actionLabel(a) }}
        </button>
        <div v-if="!data.actions.length && !data.can_edit" class="tiny muted">{{ t('rtp.noActions') }}</div>
      </div>
    </template>

    <Sheet v-if="sheet" :title="sheetTitle" @close="sheet = null">
      <div class="small" style="margin-bottom: 10px"><b>{{ name }}</b> · {{ money(d.total_payment) }}</div>
      <div v-if="sheet.action === 'Mark as Paid'" class="field">
        <label>{{ t('rtp.paymentRef') }}</label>
        <input v-model="payRef" :placeholder="t('rtp.paymentRefPh')" />
      </div>
      <div class="field">
        <label>{{ sheet.action === 'Reject' ? t('rtp.rejectReason') : t('rtp.approveNote') }}</label>
        <textarea v-model="note" rows="3"></textarea>
      </div>
      <button class="btn block" :class="actionCls(sheet.action)" :disabled="busy" @click="run(sheet.action)">
        <Icon v-if="busy" name="loading" spin /> {{ actionLabel(sheet.action) }}
      </button>
    </Sheet>

    <div v-if="preview" class="preview-mask" @click.self="closePreview">
      <div class="preview-box">
        <div class="row between" style="margin-bottom: 8px">
          <span class="small truncate">{{ preview.name }}</span>
          <button class="btn sm" @click="closePreview">{{ t('common.close') }}</button>
        </div>
        <img :src="preview.url" :alt="preview.name" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.grand-amt { font-size: 26px; font-weight: 800; margin: 10px 0 2px; }
.kv { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 12px; }
.kv > div { min-width: 0; }
.kv span { display: block; font-size: 11px; color: var(--muted); }
.kv b { display: block; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.note-box { background: var(--brand-soft); border-radius: 10px; padding: 8px 10px; }
.totals .row { padding: 4px 0; font-size: 14px; }
.totals .grand { border-top: 1px solid var(--line); margin-top: 4px; padding-top: 8px; font-size: 16px; }
.hist { padding: 6px 0; border-bottom: 1px solid var(--line); }
.hist:last-child { border-bottom: 0; }
.pi-line { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; border-top: 1px dashed var(--line, #e5e7eb); padding-top: 8px; }
.pi-badge { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; background: #fef3c7; color: #92400e; }
.pi-badge.paid { background: #dcfce7; color: #166534; }
.pi-badge.draft { background: #e5e7eb; color: #374151; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 16px 0 24px; }
.preview-mask { position: fixed; inset: 0; z-index: 60; background: rgba(0, 0, 0, .7); display: grid; place-items: center; padding: 16px; }
.preview-box { background: var(--card); border-radius: 14px; padding: 12px; max-width: 720px; width: 100%; max-height: 92vh; overflow: auto; }
.preview-box img { width: 100%; height: auto; border-radius: 8px; }
</style>
