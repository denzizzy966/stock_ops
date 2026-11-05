<script setup>
// Request to Pay — form pengajuan baru / ubah draft. Online-only.
// Urutan simpan: (1) simpan data → dapat nomor & id baris invoice, (2) unggah file baru ke
// dokumen itu, (3) simpan URL file (+ ajukan bila diminta). Server menghitung ulang semua total.
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useI18n } from '../lib/i18n'
import { getRtpSetup, getRtp, saveRtp, uploadFile } from '../lib/service'
import { fmtMoney, invoiceCalc, MAX_FILE_MB } from '../lib/rtp'
import { fileToResizedBlob, todayStr } from '../lib/util'
import AppBar from '../components/AppBar.vue'
import SearchSelect from '../components/SearchSelect.vue'

const app = useApp()
const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()

const editName = computed(() => route.params.name || '')
// Jenis pajak dipotong → akun utang pajak saat Finance membuat Purchase Invoice. Tarif awal hanya saran.
const TAX_TYPES = ['PPh 23', 'PPh 21', 'PPh 4(2)']
const DEFAULT_RATE = { 'PPh 23': 2, 'PPh 21': 2.5, 'PPh 4(2)': 10 }
function setTaxType(inv, v) {
  inv.tax_type = v || ''
  if (v && !(Number(inv.tax_rate) > 0)) inv.tax_rate = DEFAULT_RATE[v]
}
const setup = ref(null)
const loading = ref(true)
const busy = ref('')
const doc = reactive({
  name: '',
  company: '',
  employee: '',
  department: '',
  position: '',
  business_unit: '',
  payment_purpose: '',
  purpose_detail: '',
  urgency: 'Normal',
  payment_date: todayStr(),
  invoices: []
})

const blankInvoice = () => ({
  name: '', supplier: '', vendor_name: '', invoice_no: '', invoice_file: '', amount: null,
  tax_withheld: 0, tax_type: '', tax_id: '', tax_rate: null, notes: '', _file: null, _fileName: ''
})

const companies = computed(() => (setup.value?.companies || []).map((c) => c.name))
const currency = computed(() => (setup.value?.companies || []).find((c) => c.name === doc.company)?.default_currency || 'IDR')
const purposes = computed(() => setup.value?.purposes || [])
const purposeIsOther = computed(() => !!purposes.value.find((p) => p.name === doc.payment_purpose)?.is_other)
const buOptions = computed(() => (setup.value?.business_units || []).map((b) => b.name))
const suppliers = computed(() => setup.value?.suppliers || [])
const supplierLabel = (s) => (s.supplier_name && s.supplier_name !== s.name ? `${s.supplier_name} (${s.name})` : s.name)
const supplierOptions = computed(() => suppliers.value.map(supplierLabel))
const money = (v) => fmtMoney(v, currency.value, locale.value)
const totals = computed(() =>
  doc.invoices.reduce(
    (a, inv) => {
      const c = invoiceCalc(inv)
      return { amount: a.amount + c.amount, tax: a.tax + c.tax, net: a.net + c.net }
    },
    { amount: 0, tax: 0, net: 0 }
  )
)

async function loadSetup(company) {
  setup.value = await getRtpSetup(company || undefined)
  if (!doc.company) doc.company = setup.value.company || ''
}

async function changeCompany(c) {
  if (c === doc.company) return
  doc.company = c
  doc.department = doc.business_unit = ''
  await loadSetup(c)
  const d = setup.value.defaults || {}
  doc.department = d.department || ''
  doc.business_unit = d.business_unit || ''
}

onMounted(async () => {
  try {
    if (editName.value) {
      const r = await getRtp(editName.value)
      if (!r.can_edit) {
        app.notify(t('rtp.noActions'), 'error')
        return router.replace('/rtp/' + encodeURIComponent(editName.value))
      }
      const d = r.doc
      Object.assign(doc, {
        name: d.name, company: d.company, employee: d.employee || '', department: d.department || '',
        position: d.position || '', business_unit: d.business_unit || '', payment_purpose: d.payment_purpose || '',
        purpose_detail: d.purpose_detail || '', urgency: d.urgency || 'Normal', payment_date: d.payment_date || todayStr(),
        invoices: (d.invoices || []).map((i) => ({ ...blankInvoice(), ...i, tax_withheld: i.tax_withheld ? 1 : 0 }))
      })
      await loadSetup(d.company)
    } else {
      await loadSetup()
      const d = setup.value.defaults || {}
      Object.assign(doc, {
        department: d.department || '', position: d.position || '', business_unit: d.business_unit || '', employee: d.employee || ''
      })
      doc.invoices = [blankInvoice()]
    }
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  } finally {
    loading.value = false
  }
})

function pickSupplier(inv, label) {
  const s = suppliers.value.find((x) => supplierLabel(x) === label)
  inv.supplier = s ? s.name : ''
  if (s) {
    inv.vendor_name = s.supplier_name || s.name
    if (s.tax_id && !inv.tax_id) inv.tax_id = s.tax_id
  }
}
const supplierValue = (inv) => {
  const s = suppliers.value.find((x) => x.name === inv.supplier)
  return s ? supplierLabel(s) : ''
}

// File invoice: gambar diperkecil (hemat kuota), PDF dikirim apa adanya.
const fileInputs = ref({})
const camInputs = ref({})
async function onFile(inv, ev) {
  const f = ev.target.files && ev.target.files[0]
  ev.target.value = ''
  if (!f) return
  if (f.size > MAX_FILE_MB * 1024 * 1024) return app.notify(t('rtp.fileTooBig', { mb: MAX_FILE_MB }), 'error')
  let blob = f
  let name = f.name || 'invoice.jpg'
  if (f.type && f.type.startsWith('image/')) {
    try {
      blob = await fileToResizedBlob(f, 2000, 0.82)
      name = name.replace(/\.[^.]+$/, '') + '.jpg'
    } catch {
      blob = f
    }
  }
  inv._file = blob
  inv._fileName = name
}
const fileLabel = (inv) => inv._fileName || (inv.invoice_file ? inv.invoice_file.split('/').pop() : '')

function validate(submit) {
  if (!doc.department) return t('rtp.vDept')
  if (!doc.business_unit) return t('rtp.vBu')
  if (!doc.payment_purpose) return t('rtp.vPurpose')
  if (purposeIsOther.value && !doc.purpose_detail.trim()) return t('rtp.vPurposeDetail')
  if (!doc.payment_date) return t('rtp.vDate')
  if (!doc.invoices.length) return t('rtp.vInvoice')
  for (const [i, inv] of doc.invoices.entries()) {
    const n = i + 1
    if (!String(inv.vendor_name || '').trim()) return t('rtp.vVendor', { n })
    if (!(Number(inv.amount) > 0)) return t('rtp.vAmount', { n })
    if (inv.tax_withheld && (!inv.tax_type || !String(inv.tax_id || '').trim() || !(Number(inv.tax_rate) > 0 && Number(inv.tax_rate) < 100)))
      return t('rtp.vTax', { n })
    if (submit && !inv.invoice_file && !inv._file) return t('rtp.vFile', { n })
  }
  return ''
}

const payload = () => ({
  name: doc.name || undefined,
  company: doc.company, employee: doc.employee || null, department: doc.department, position: doc.position,
  business_unit: doc.business_unit, payment_purpose: doc.payment_purpose,
  purpose_detail: purposeIsOther.value ? doc.purpose_detail : '', urgency: doc.urgency, payment_date: doc.payment_date,
  invoices: doc.invoices.map((i) => ({
    name: i.name || undefined, supplier: i.supplier || null, vendor_name: i.vendor_name, invoice_no: i.invoice_no,
    invoice_file: i.invoice_file || null, amount: Number(i.amount) || 0, tax_withheld: i.tax_withheld ? 1 : 0,
    tax_type: i.tax_withheld ? i.tax_type || null : null, tax_id: i.tax_withheld ? i.tax_id : '', tax_rate: i.tax_withheld ? Number(i.tax_rate) || 0 : 0, notes: i.notes
  }))
})

async function save(submit) {
  const err = validate(submit)
  if (err) return app.notify(err, 'error')
  if (!app.online) return app.notify(t('rtp.onlineOnly'), 'error')
  busy.value = submit ? 'submit' : 'draft'
  try {
    const pending = doc.invoices.filter((i) => i._file)
    let r = await saveRtp(payload(), pending.length ? 0 : submit ? 1 : 0)
    doc.name = r.name
    r.invoices.forEach((rowName, idx) => doc.invoices[idx] && (doc.invoices[idx].name = rowName))
    if (pending.length) {
      for (const [k, inv] of pending.entries()) {
        app.notify(t('rtp.uploading', { n: k + 1, total: pending.length }))
        const up = await uploadFile(inv._file, { doctype: 'Request to Pay', docname: doc.name, filename: inv._fileName })
        inv.invoice_file = up.file_url
        inv._file = null
      }
      r = await saveRtp(payload(), submit ? 1 : 0)
    }
    app.notify(t(submit ? 'rtp.submitted' : 'rtp.saved', { name: r.name }), 'success')
    router.replace('/rtp/' + encodeURIComponent(r.name))
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  } finally {
    busy.value = ''
  }
}
</script>

<template>
  <AppBar :title="editName ? t('rtp.editTitle', { name: editName }) : t('rtp.newTitle')" back />
  <div class="content">
    <div v-if="!app.online" class="card" style="color: var(--warn); font-weight: 600">{{ t('rtp.onlineOnly') }}</div>
    <div v-if="loading" class="empty"><div class="big"><Icon name="loading" spin /></div>{{ t('common.loading') }}</div>
    <template v-else-if="setup">
      <div class="card">
        <div v-if="companies.length > 1" class="field">
          <label>{{ t('rtp.company') }}</label>
          <SearchSelect :model-value="doc.company" :options="companies" :disabled="!!doc.name" @update:model-value="changeCompany" />
        </div>
        <div v-else class="tiny muted" style="margin-bottom: 10px">{{ doc.company }} · {{ currency }}</div>
        <div class="field">
          <label>{{ t('rtp.department') }}</label>
          <SearchSelect v-model="doc.department" :options="setup.departments" :placeholder="t('rtp.department')" />
        </div>
        <div class="field">
          <label>{{ t('rtp.position') }} <span class="muted">({{ t('common.optional') }})</span></label>
          <input v-model="doc.position" />
        </div>
        <div class="field" style="margin-bottom: 0">
          <label>{{ t('rtp.businessUnit') }}</label>
          <SearchSelect v-model="doc.business_unit" :options="buOptions" :placeholder="t('rtp.businessUnit')" />
        </div>
      </div>

      <div class="card mt12">
        <div class="field">
          <label>{{ t('rtp.purpose') }}</label>
          <SearchSelect v-model="doc.payment_purpose" :options="purposes.map((p) => p.name)" :placeholder="t('rtp.purpose')" />
        </div>
        <div v-if="purposeIsOther" class="field">
          <label>{{ t('rtp.purposeDetail') }}</label>
          <textarea v-model="doc.purpose_detail" rows="2"></textarea>
        </div>
        <div class="field">
          <label>{{ t('rtp.urgency') }}</label>
          <div class="seg">
            <button type="button" :class="{ active: doc.urgency === 'Normal' }" @click="doc.urgency = 'Normal'">{{ t('rtp.normal') }}</button>
            <button type="button" :class="{ active: doc.urgency === 'Urgent' }" @click="doc.urgency = 'Urgent'">{{ t('rtp.urgent') }}</button>
          </div>
        </div>
        <div class="field" style="margin-bottom: 0">
          <label>{{ t('rtp.paymentDate') }}</label>
          <input type="date" v-model="doc.payment_date" />
        </div>
      </div>

      <div class="section-title">{{ t('rtp.invoices') }} ({{ doc.invoices.length }})</div>
      <div v-for="(inv, i) in doc.invoices" :key="i" class="card mt12">
        <div class="row between" style="margin-bottom: 8px">
          <b>{{ t('rtp.invoiceN', { n: i + 1 }) }}</b>
          <button v-if="doc.invoices.length > 1" type="button" class="btn sm danger" :aria-label="t('rtp.removeInvoice')" @click="doc.invoices.splice(i, 1)">
            <Icon name="trash" />
          </button>
        </div>
        <div v-if="suppliers.length" class="field">
          <label>{{ t('rtp.supplier') }} <span class="muted">({{ t('rtp.supplierHint') }})</span></label>
          <SearchSelect :model-value="supplierValue(inv)" :options="supplierOptions" clearable @update:model-value="(v) => pickSupplier(inv, v)" />
        </div>
        <div class="field">
          <label>{{ t('rtp.vendor') }}</label>
          <input v-model="inv.vendor_name" />
        </div>
        <div class="field">
          <label>{{ t('rtp.invoiceNo') }} <span class="muted">({{ t('common.optional') }})</span></label>
          <input v-model="inv.invoice_no" />
        </div>
        <div class="field">
          <label>{{ t('rtp.file') }}</label>
          <div class="row" style="gap: 8px; flex-wrap: wrap">
            <span v-if="fileLabel(inv)" class="file-chip"><Icon name="receipt" /> {{ fileLabel(inv) }}</span>
            <button type="button" class="btn sm" @click="fileInputs[i] && fileInputs[i].click()">
              <Icon name="gallery" /> {{ fileLabel(inv) ? t('rtp.replaceFile') : t('rtp.pickFile') }}
            </button>
            <button type="button" class="btn sm" @click="camInputs[i] && camInputs[i].click()"><Icon name="camera" /> {{ t('rtp.camera') }}</button>
          </div>
          <input :ref="(el) => (fileInputs[i] = el)" type="file" accept="image/*,application/pdf" hidden @change="(e) => onFile(inv, e)" />
          <input :ref="(el) => (camInputs[i] = el)" type="file" accept="image/*" capture="environment" hidden @change="(e) => onFile(inv, e)" />
        </div>
        <div class="field">
          <label>{{ t('rtp.amount') }} ({{ currency }})</label>
          <input v-model.number="inv.amount" type="number" inputmode="decimal" min="0" step="any" />
        </div>
        <label class="row between" style="margin-bottom: 12px; gap: 10px">
          <span class="small" style="font-weight: 600">{{ t('rtp.taxWithheld') }}</span>
          <span class="switch"><input type="checkbox" :checked="!!inv.tax_withheld" @change="inv.tax_withheld = $event.target.checked ? 1 : 0" /><span class="slider"></span></span>
        </label>
        <template v-if="inv.tax_withheld">
          <div class="field">
            <label>{{ t('rtp.taxType') }}</label>
            <SearchSelect :model-value="inv.tax_type" :options="TAX_TYPES" :placeholder="t('rtp.taxType')" @update:model-value="(v) => setTaxType(inv, v)" />
            <div class="tiny muted" style="margin-top: 4px">{{ t('rtp.taxTypeHint') }}</div>
          </div>
          <div class="field">
            <label>{{ t('rtp.taxId') }}</label>
            <input v-model="inv.tax_id" />
          </div>
          <div class="field">
            <label>{{ t('rtp.taxRate') }}</label>
            <input v-model.number="inv.tax_rate" type="number" inputmode="decimal" min="0" max="100" step="any" placeholder="2.5" />
          </div>
        </template>
        <div class="field">
          <label>{{ t('rtp.notes') }} <span class="muted">({{ t('common.optional') }})</span></label>
          <textarea v-model="inv.notes" rows="2"></textarea>
        </div>
        <div class="calc">
          <span v-if="inv.tax_withheld">{{ t('rtp.taxAmount') }}: <b>{{ money(invoiceCalc(inv).tax) }}</b></span>
          <span>{{ t('rtp.net') }}: <b>{{ money(invoiceCalc(inv).net) }}</b></span>
        </div>
      </div>
      <button type="button" class="btn block mt12" @click="doc.invoices.push(blankInvoice())"><Icon name="plus" /> {{ t('rtp.addInvoice') }}</button>

      <div class="card mt12 totals">
        <div class="row between"><span>{{ t('rtp.totalInvoice') }}</span><b>{{ money(totals.amount) }}</b></div>
        <div class="row between"><span>{{ t('rtp.totalTax') }}</span><b>− {{ money(totals.tax) }}</b></div>
        <div class="row between grand"><span>{{ t('rtp.totalPayment') }}</span><b>{{ money(totals.net) }}</b></div>
      </div>

      <div class="row" style="gap: 8px; margin: 14px 0 24px">
        <button class="btn grow" :disabled="!!busy || !app.online" @click="save(false)">
          <Icon v-if="busy === 'draft'" name="loading" spin /> {{ t('rtp.saveDraft') }}
        </button>
        <button class="btn brand grow" :disabled="!!busy || !app.online" @click="save(true)">
          <Icon v-if="busy === 'submit'" name="loading" spin /> {{ t('rtp.submit') }}
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.file-chip {
  display: inline-flex; align-items: center; gap: 6px; max-width: 100%; padding: 6px 10px; border-radius: 10px;
  background: var(--brand-soft); font-size: 12px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.calc { display: flex; justify-content: flex-end; gap: 14px; flex-wrap: wrap; font-size: 13px; }
.totals .row { padding: 4px 0; font-size: 14px; }
.totals .grand { border-top: 1px solid var(--line); margin-top: 4px; padding-top: 8px; font-size: 16px; }
</style>
