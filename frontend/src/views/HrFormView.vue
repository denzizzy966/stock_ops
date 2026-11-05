<script setup>
// Menu HR — form Klaim Biaya (Expense Claim) / Kasbon (Employee Advance). Online-only.
// Simpan = kirim ke Expense Approver (standar HRMS: draft langsung dibagikan ke approver).
// Urutan: (1) simpan → dapat nomor dokumen, (2) unggah nota baru ke dokumen itu.
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useI18n } from '../lib/i18n'
import { getHrSetup, getHr, saveHr, uploadFile } from '../lib/service'
import { fmtMoney, MAX_FILE_MB } from '../lib/rtp'
import { HR_KINDS } from '../lib/hr'
import { fileToResizedBlob, todayStr } from '../lib/util'
import AppBar from '../components/AppBar.vue'
import SearchSelect from '../components/SearchSelect.vue'

const app = useApp()
const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()

const kind = computed(() => route.params.kind)
const isClaim = computed(() => kind.value === 'claim')
const editName = computed(() => route.params.name || '')
const setup = ref(null)
const loading = ref(true)
const busy = ref(false)
const blankRow = () => ({ expense_date: todayStr(), expense_type: '', description: '', amount: null })
const doc = reactive({ name: '', remark: '', expenses: [], use_advances: 0, purpose: '', advance_amount: null })
const newFiles = ref([]) // [{blob, name, preview}]
const existingFiles = ref([])
const money = (v) => fmtMoney(v, setup.value?.currency, locale.value)

const types = computed(() => (setup.value?.expense_types || []).map((x) => x.name))
const noAccount = (name) => {
  const x = (setup.value?.expense_types || []).find((y) => y.name === name)
  return x && !x.has_account
}
const total = computed(() => doc.expenses.reduce((a, r) => a + (Number(r.amount) || 0), 0))
const advanceLeft = computed(() => (setup.value?.advances || []).reduce((a, r) => a + (Number(r.unclaimed) || 0), 0))
const blocked = computed(() => !setup.value || !setup.value.approver)

onMounted(async () => {
  try {
    setup.value = await getHrSetup(kind.value)
    if (editName.value) {
      const r = await getHr(kind.value, editName.value)
      const d = r.doc
      doc.name = d.name
      if (isClaim.value) {
        doc.remark = d.remark || ''
        doc.expenses = (d.expenses || []).map((x) => ({
          expense_date: x.expense_date, expense_type: x.expense_type,
          description: String(x.description || '').replace(/<[^>]+>/g, ''), amount: x.amount
        }))
        doc.use_advances = (d.advances || []).length ? 1 : 0
      } else {
        doc.purpose = d.purpose || ''
        doc.advance_amount = d.advance_amount
      }
      existingFiles.value = r.files || []
    } else if (isClaim.value) {
      doc.expenses = [blankRow()]
    }
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  } finally {
    loading.value = false
  }
})

// Nota: gambar diperkecil (hemat kuota), PDF apa adanya.
const fileInput = ref(null)
const camInput = ref(null)
async function onFile(ev) {
  const files = [...(ev.target.files || [])]
  ev.target.value = ''
  for (const f of files) {
    if (f.size > MAX_FILE_MB * 1024 * 1024) {
      app.notify(t('rtp.fileTooBig', { mb: MAX_FILE_MB }), 'error')
      continue
    }
    let blob = f
    let name = f.name || 'nota.jpg'
    if (f.type && f.type.startsWith('image/')) {
      try {
        blob = await fileToResizedBlob(f, 2000, 0.82)
        name = name.replace(/\.[^.]+$/, '') + '.jpg'
      } catch {
        blob = f
      }
    }
    newFiles.value.push({ blob, name, preview: blob.type && blob.type.startsWith('image/') ? URL.createObjectURL(blob) : '' })
  }
}
function removeNew(i) {
  const f = newFiles.value[i]
  if (f && f.preview) URL.revokeObjectURL(f.preview)
  newFiles.value.splice(i, 1)
}

function validate() {
  if (isClaim.value) {
    if (!doc.expenses.length) return t('hr.vNoRow')
    for (const [i, r] of doc.expenses.entries())
      if (!r.expense_type || !r.expense_date || !(Number(r.amount) > 0)) return t('hr.vExpense', { n: i + 1 })
  } else if (!String(doc.purpose || '').trim() || !(Number(doc.advance_amount) > 0)) return t('hr.vAdvance')
  return ''
}
const payload = () =>
  isClaim.value
    ? {
        name: doc.name || undefined, remark: doc.remark, use_advances: doc.use_advances ? 1 : 0,
        expenses: doc.expenses.map((r) => ({ ...r, amount: Number(r.amount) || 0 }))
      }
    : { name: doc.name || undefined, purpose: doc.purpose, advance_amount: Number(doc.advance_amount) || 0 }

async function save() {
  const err = validate()
  if (err) return app.notify(err, 'error')
  if (!app.online) return app.notify(t('hr.onlineOnly'), 'error')
  busy.value = true
  try {
    const r = await saveHr(kind.value, payload())
    doc.name = r.name
    for (const [k, f] of newFiles.value.entries()) {
      app.notify(t('hr.uploading', { n: k + 1, total: newFiles.value.length }))
      await uploadFile(f.blob, { doctype: setup.value.doctype, docname: r.name, filename: f.name })
    }
    newFiles.value = []
    app.notify(t('hr.sent', { name: r.name }), 'success')
    router.replace(`/hr/${kind.value}/${encodeURIComponent(r.name)}`)
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <AppBar :title="editName ? t('hr.edit.' + kind) : t('hr.new.' + kind)" back />
  <div class="content">
    <div v-if="loading" class="empty"><div class="big"><Icon name="loading" spin /></div>{{ t('common.loading') }}</div>
    <template v-else-if="setup">
      <div class="card">
        <div class="kv">
          <div><span>{{ t('hr.employee') }}</span><b>{{ setup.employee.employee_name }}</b></div>
          <div><span>Company</span><b>{{ setup.employee.company }}</b></div>
          <div><span>{{ t('hr.approver') }}</span><b>{{ setup.approver_name || setup.approver || '—' }}</b></div>
        </div>
        <div v-if="blocked" class="warn-box mt12">{{ t('hr.noApprover') }}</div>
      </div>

      <!-- Klaim biaya -->
      <template v-if="isClaim">
        <div class="section-title">{{ t('hr.expenses') }}</div>
        <div v-for="(r, i) in doc.expenses" :key="i" class="card mt12 exp-card">
          <div class="row between" style="margin-bottom: 8px">
            <b class="small">#{{ i + 1 }}</b>
            <button v-if="doc.expenses.length > 1" type="button" class="btn sm" @click="doc.expenses.splice(i, 1)"><Icon name="trash" /></button>
          </div>
          <div class="field">
            <label>{{ t('hr.expType') }}</label>
            <SearchSelect v-model="r.expense_type" :options="types" :placeholder="t('hr.expType')" />
            <div v-if="r.expense_type && noAccount(r.expense_type)" class="tiny" style="margin-top: 4px; color: var(--warn)">⚠ {{ t('hr.noAccount') }}</div>
          </div>
          <div class="row" style="gap: 8px">
            <div class="field grow">
              <label>{{ t('hr.expDate') }}</label>
              <input v-model="r.expense_date" type="date" :max="todayStr()" />
            </div>
            <div class="field grow">
              <label>{{ t('hr.amount') }} ({{ setup.currency }})</label>
              <input v-model.number="r.amount" type="number" inputmode="decimal" min="0" step="any" />
            </div>
          </div>
          <div class="field">
            <label>{{ t('hr.expDesc') }} <span class="muted">({{ t('common.optional') }})</span></label>
            <input v-model="r.description" />
          </div>
        </div>
        <button type="button" class="btn block mt12" @click="doc.expenses.push(blankRow())"><Icon name="plus" /> {{ t('hr.addExpense') }}</button>

        <div class="card mt12 totals">
          <div class="row between grand"><span>{{ t('hr.total') }}</span><b>{{ money(total) }}</b></div>
          <label v-if="advanceLeft > 0" class="row between" style="margin-top: 10px; gap: 10px">
            <span class="small">{{ t('hr.useAdvance') }}<br /><span class="tiny muted">{{ t('hr.advanceLeft', { amount: money(advanceLeft) }) }}</span></span>
            <span class="switch"><input type="checkbox" :checked="!!doc.use_advances" @change="doc.use_advances = $event.target.checked ? 1 : 0" /><span class="slider"></span></span>
          </label>
        </div>
        <div class="field mt12">
          <label>{{ t('hr.remark') }} <span class="muted">({{ t('common.optional') }})</span></label>
          <textarea v-model="doc.remark" rows="2"></textarea>
        </div>
      </template>

      <!-- Kasbon -->
      <template v-else>
        <div class="card mt12">
          <div class="field">
            <label>{{ t('hr.purpose') }}</label>
            <textarea v-model="doc.purpose" rows="3"></textarea>
          </div>
          <div class="field">
            <label>{{ t('hr.advAmount') }} ({{ setup.currency }})</label>
            <input v-model.number="doc.advance_amount" type="number" inputmode="decimal" min="0" step="any" />
          </div>
        </div>
      </template>

      <!-- Nota / lampiran -->
      <div class="section-title">{{ t('hr.receipts') }}</div>
      <div class="card">
        <div v-if="existingFiles.length" class="tiny muted" style="margin-bottom: 6px">
          <div v-for="f in existingFiles" :key="f.name">📎 {{ f.file_name }}</div>
        </div>
        <div class="thumbs">
          <div v-for="(f, i) in newFiles" :key="i" class="thumb">
            <img v-if="f.preview" :src="f.preview" alt="" />
            <span v-else class="tiny">{{ f.name }}</span>
            <button type="button" class="thumb-x" @click="removeNew(i)" :aria-label="t('common.delete')">×</button>
          </div>
        </div>
        <div class="row" style="gap: 8px; margin-top: 8px">
          <button type="button" class="btn sm grow" @click="camInput && camInput.click()"><Icon name="camera" /> {{ t('hr.camera') }}</button>
          <button type="button" class="btn sm grow" @click="fileInput && fileInput.click()"><Icon name="gallery" /> {{ t('hr.file') }}</button>
        </div>
        <input ref="fileInput" type="file" accept="image/*,application/pdf" multiple hidden @change="onFile" />
        <input ref="camInput" type="file" accept="image/*" capture="environment" hidden @change="onFile" />
      </div>

      <div class="tiny muted mt12">{{ t('hr.sendHint') }}</div>
      <button class="btn brand block mt12" :disabled="busy || blocked" @click="save">
        <Icon :name="busy ? 'loading' : 'check'" :spin="busy" /> {{ t('hr.send') }}
      </button>
      <div style="height: 24px"></div>
    </template>
  </div>
</template>

<style scoped>
.kv { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 12px; }
.kv > div { min-width: 0; }
.kv span { display: block; font-size: 11px; color: var(--muted); }
.kv b { display: block; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.warn-box { background: color-mix(in srgb, var(--warn) 14%, transparent); color: var(--warn); border-radius: 10px; padding: 10px 12px; font-size: 13px; font-weight: 600; }
.totals .grand { font-size: 15px; }
.thumbs { display: flex; flex-wrap: wrap; gap: 8px; }
.thumb { position: relative; width: 72px; height: 72px; border-radius: 10px; overflow: hidden; background: var(--line); display: grid; place-items: center; }
.thumb img { width: 100%; height: 100%; object-fit: cover; }
.thumb-x { position: absolute; top: 2px; right: 2px; width: 22px; height: 22px; border-radius: 50%; border: 0; background: rgba(0, 0, 0, 0.6); color: #fff; font-size: 15px; line-height: 1; cursor: pointer; }
</style>
