<script setup>
// Menu HR — detail Klaim Biaya / Kasbon + aksi (Setujui / Tolak oleh Expense Approver, Batalkan oleh karyawan).
// Aksi yang tampil datang dari server, jadi selalu sesuai hak user.
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { getHr, hrAction, getHrFile } from '../lib/service'
import { fmtMoney } from '../lib/rtp'
import { HR_KINDS, HR_ACTIONS, hrStatus } from '../lib/hr'
import { fmtDateTime } from '../lib/util'
import AppBar from '../components/AppBar.vue'
import Sheet from '../components/Sheet.vue'

const app = useApp()
const master = useMaster()
const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()

const kind = computed(() => route.params.kind)
const isClaim = computed(() => kind.value === 'claim')
const name = computed(() => route.params.name)
const data = ref(null)
const loading = ref(true)
const busy = ref(false)
const d = computed(() => (data.value ? data.value.doc : {}))
const money = (v) => fmtMoney(v, d.value.currency, locale.value)
const st = computed(() => hrStatus(d.value))
const plain = (html) => String(html || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()

async function load() {
  loading.value = true
  try {
    data.value = await getHr(kind.value, name.value)
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  } finally {
    loading.value = false
  }
}
onMounted(load)
// Router memakai ulang komponen ini saat pindah klaim → kasbon / dokumen lain (mis. dari notifikasi).
watch(
  () => [route.params.kind, route.params.name],
  ([k, n], [k0, n0]) => {
    if (n && (k !== k0 || n !== n0)) {
      data.value = null
      sheet.value = null
      closePreview()
      load()
    }
  }
)

const sheet = ref(null) // { action }
const note = ref('')
function startAction(action) {
  note.value = ''
  sheet.value = { action }
}
const sheetTitle = computed(() => {
  const a = sheet.value && sheet.value.action
  return a === 'Reject' ? t('hr.rejectTitle') : a === 'Discard' ? t('hr.discardTitle') : t('hr.approveTitle')
})
async function run(action) {
  if (action === 'Reject' && !note.value.trim()) return app.notify(t('hr.reasonReq'), 'error')
  busy.value = true
  try {
    const r = await hrAction(kind.value, name.value, action, note.value.trim() || undefined)
    sheet.value = null
    await load()
    app.notify(t('hr.done', { name: r.name, status: t('hr.status.' + hrStatus(d.value).key) }), 'success')
    if (action !== 'Discard' && master.hr[kind.value]) master.hr[kind.value].todo = Math.max(0, (master.hr[kind.value].todo || 1) - 1)
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  } finally {
    busy.value = false
  }
}
const actionLabel = (a) => (HR_ACTIONS[a] ? t('hr.action.' + HR_ACTIONS[a].key) : a)
const actionCls = (a) => (HR_ACTIONS[a] ? HR_ACTIONS[a].cls : '')

// Pratinjau nota lewat endpoint ber-izin (APK tidak bisa memakai URL /private langsung).
const preview = ref(null)
async function openFile(f) {
  try {
    const blob = await getHrFile(kind.value, name.value, f.file_url)
    const url = URL.createObjectURL(blob)
    if (!(blob.type || '').startsWith('image/')) {
      window.open(url, '_blank')
      setTimeout(() => URL.revokeObjectURL(url), 60000)
      return
    }
    preview.value = { url, name: f.file_name }
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  }
}
function closePreview() {
  if (preview.value) URL.revokeObjectURL(preview.value.url)
  preview.value = null
}
onBeforeUnmount(closePreview)

const amount = computed(() => (isClaim.value ? d.value.total_claimed_amount : d.value.advance_amount))
const paid = computed(() => ['Paid', 'Claimed', 'Returned', 'Partly Claimed and Returned'].includes(d.value.status))
</script>

<template>
  <AppBar :title="name" back />
  <div class="content">
    <div v-if="loading && !data" class="empty"><div class="big"><Icon name="loading" spin /></div>{{ t('common.loading') }}</div>
    <template v-else-if="data">
      <div class="card">
        <span class="badge-status" :class="st.cls">{{ t('hr.status.' + st.key) }}</span>
        <div class="grand-amt">{{ money(amount) }}</div>
        <div class="small">{{ isClaim ? d.remark || t('hr.menu.claim') : d.purpose }}</div>
        <div class="kv mt12">
          <div><span>{{ t('hr.employee') }}</span><b>{{ d.employee_name }}</b></div>
          <div><span>Company</span><b>{{ d.company }}</b></div>
          <div><span>{{ t('hr.expDate') }}</span><b>{{ d.posting_date }}</b></div>
          <div><span>{{ t('hr.approver') }}</span><b>{{ d.approver_name || d.approver || '—' }}</b></div>
          <template v-if="isClaim && d.docstatus === 1">
            <div><span>{{ t('hr.sanctioned') }}</span><b>{{ money(d.total_sanctioned_amount) }}</b></div>
            <div v-if="d.total_advance_amount"><span>{{ t('hr.advanceUsed') }}</span><b>− {{ money(d.total_advance_amount) }}</b></div>
            <div><span>{{ t('hr.toPay') }}</span><b>{{ money(d.grand_total) }}</b></div>
          </template>
          <template v-if="!isClaim && d.docstatus === 1">
            <div><span>{{ t('hr.paidAmount') }}</span><b>{{ money(d.paid_amount) }}</b></div>
            <div><span>{{ t('hr.claimed') }}</span><b>{{ money(d.claimed_amount) }}</b></div>
          </template>
        </div>
        <div v-if="d.docstatus === 1 && !paid && st.key !== 'rejected'" class="tiny muted mt8">{{ t('hr.payNote') }}</div>
      </div>

      <template v-if="isClaim">
        <div class="section-title">{{ t('hr.expenses') }} ({{ (d.expenses || []).length }})</div>
        <div v-for="r in d.expenses" :key="r.name" class="card mt12">
          <div class="row between" style="gap: 8px">
            <div style="min-width: 0">
              <div class="truncate" style="font-weight: 700">{{ r.expense_type }}</div>
              <div class="tiny muted">{{ r.expense_date }}<template v-if="plain(r.description) && plain(r.description) !== r.expense_type"> · {{ plain(r.description) }}</template></div>
            </div>
            <b>{{ money(r.amount) }}</b>
          </div>
        </div>
      </template>

      <template v-if="data.files.length">
        <div class="section-title">{{ t('hr.receipts') }}</div>
        <div class="card">
          <div v-for="f in data.files" :key="f.name" class="row between file-row">
            <span class="small truncate">📎 {{ f.file_name }}</span>
            <button class="btn sm" @click="openFile(f)"><Icon name="eye" /> {{ t('hr.viewFile') }}</button>
          </div>
        </div>
      </template>

      <template v-if="data.history.length">
        <div class="section-title">{{ t('hr.history') }}</div>
        <div class="card">
          <div v-for="(h, i) in data.history" :key="i" class="hist">
            <div class="small"><b>{{ h.owner_name }}</b> · {{ h.content }}</div>
            <div class="tiny muted">{{ fmtDateTime(h.creation) }}</div>
          </div>
        </div>
      </template>

      <div class="actions">
        <button v-if="data.can_edit" class="btn grow" :disabled="busy" @click="router.push(`/hr/${kind}/${encodeURIComponent(name)}/edit`)">
          <Icon name="note" /> {{ t('rtp.edit') }}
        </button>
        <button v-for="a in data.actions" :key="a" class="btn grow" :class="actionCls(a)" :disabled="busy" @click="startAction(a)">
          {{ actionLabel(a) }}
        </button>
        <div v-if="!data.actions.length && !data.can_edit" class="tiny muted">{{ t('hr.noActions') }}</div>
      </div>
    </template>

    <Sheet v-if="sheet" :title="sheetTitle" @close="sheet = null">
      <div class="small" style="margin-bottom: 8px">{{ name }} · {{ money(amount) }}</div>
      <div class="field">
        <label>{{ sheet.action === 'Reject' ? t('hr.reason') : t('hr.notePh') }}</label>
        <textarea v-model="note" rows="3"></textarea>
      </div>
      <button class="btn block" :class="actionCls(sheet.action) || 'brand'" :disabled="busy" @click="run(sheet.action)">
        <Icon v-if="busy" name="loading" spin /> {{ actionLabel(sheet.action) }}
      </button>
    </Sheet>

    <div v-if="preview" class="preview" @click="closePreview">
      <img :src="preview.url" :alt="preview.name" />
    </div>
  </div>
</template>

<style scoped>
.kv { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 12px; }
.kv > div { min-width: 0; }
.kv span { display: block; font-size: 11px; color: var(--muted); }
.kv b { display: block; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.grand-amt { font-size: 26px; font-weight: 800; margin: 8px 0 2px; }
.file-row { gap: 8px; padding: 6px 0; }
.file-row + .file-row { border-top: 1px solid var(--line); }
.hist + .hist { margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--line); }
.actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 16px 0 24px; }
.preview { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.85); display: grid; place-items: center; z-index: 60; padding: 16px; }
.preview img { max-width: 100%; max-height: 100%; border-radius: 8px; }
</style>
