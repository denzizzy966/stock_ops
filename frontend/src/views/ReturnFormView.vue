<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { DOC_TYPES } from '../data/mock'
import { useApp } from '../stores/app'
import { useDocs } from '../stores/docs'
import { useI18n } from '../lib/i18n'
import { getGeolocation } from '../lib/util'
import { getReceiptItemsForReturn } from '../lib/service'
import AppBar from '../components/AppBar.vue'
import PhotoUploader from '../components/PhotoUploader.vue'
import ReceiptSheet from '../components/ReceiptSheet.vue'

const router = useRouter()
const app = useApp()
const docs = useDocs()
const { t } = useI18n()

const cfg = DOC_TYPES.RET
const doc = reactive(docs.newDraft('RET'))

const showReceipt = ref(false)
const loadingReceipt = ref(false)
const saving = ref(false)
const locating = ref(false)

const totalQty = computed(() => doc.items.reduce((s, i) => s + (Number(i.qty) || 0), 0))
// Retur wajib online (kunci stok real-time) — tak bisa masuk outbox offline.
const blockedOffline = computed(() => !!(cfg.onlineOnly && !app.online))

// Pilih Purchase Receipt asal → tarik item + sisa qty yang masih bisa diretur.
async function selectReceipt(r) {
  showReceipt.value = false
  loadingReceipt.value = true
  try {
    const res = await getReceiptItemsForReturn(r.name)
    doc.returnAgainst = res.name
    if (res.company) doc.company = res.company
    if (res.supplier) doc.supplier = res.supplier
    // qty default = sisa yang bisa diretur; item habis retur (0) tetap ditampilkan tapi nonaktif
    doc.items = (res.items || []).map((i) => ({
      item_code: i.item_code,
      item_name: i.item_name,
      uom: i.uom,
      receivedQty: Number(i.qty) || 0,
      returnableQty: Number(i.returnable_qty) || 0,
      qty: Number(i.returnable_qty) || 0
    }))
    app.notify(t('ret.loaded', { n: doc.items.length, pr: res.name }), 'success')
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  } finally {
    loadingReceipt.value = false
  }
}
function clearReceipt() {
  doc.returnAgainst = ''
  doc.items = []
}
function clampLine(line) {
  let v = Number(line.qty) || 0
  if (v < 0) v = 0
  if (v > line.returnableQty) v = line.returnableQty
  line.qty = v
}

async function captureLocation(silent = false) {
  locating.value = true
  const g = await getGeolocation()
  locating.value = false
  if (g) {
    doc.geo = g
    if (!silent) app.notify(g, 'success')
  } else if (!silent) {
    app.notify(t('form.locationOff'), 'warn')
  }
}
function tagLocation() {
  captureLocation(false)
}
// Otomatis minta izin + ambil lokasi saat form dibuka (senyap; tombol tetap bisa re-tag).
onMounted(() => {
  if (!doc.geo) captureLocation(true)
})

function valid() {
  if (!doc.returnAgainst) return t('ret.vReceipt')
  const active = doc.items.filter((i) => Number(i.qty) > 0)
  if (!active.length) return t('ret.vQty')
  if (doc.items.some((i) => Number(i.qty) > i.returnableQty)) return t('ret.vOver')
  return null
}

async function save() {
  const err = valid()
  if (err) return app.notify(err, 'warn')
  if (blockedOffline.value) return app.notify(t('form.onlineOnly', { doc: t('docType.RET') }), 'error')
  // Kirim hanya baris dengan qty > 0
  doc.items = doc.items.filter((i) => Number(i.qty) > 0)
  saving.value = true
  const saved = await docs.save({ ...doc })
  saving.value = false
  if (saved) router.replace(`/doc/${doc.localId}`)
}
</script>

<template>
  <AppBar :title="t('docType.RET') + ' · ' + t('form.newSuffix')" back />
  <div class="content">
    <div class="card">
      <div class="row" style="gap: 10px; margin-bottom: 12px">
        <span class="lead-icon" :style="{ background: cfg.color }"><Icon :name="cfg.icon" /></span>
        <div class="grow">
          <div style="font-weight: 700">{{ t('docType.RET') }}</div>
          <div class="tiny muted">{{ cfg.doctype }} · is_return</div>
        </div>
      </div>

      <div class="field">
        <label>{{ t('ret.receipt') }}</label>
        <div v-if="doc.returnAgainst" class="row between" style="gap: 8px; align-items: center">
          <span class="po-chip"><Icon name="box" /> {{ doc.returnAgainst }}</span>
          <button class="btn sm" @click="clearReceipt">{{ t('common.clear') }}</button>
        </div>
        <button v-else class="btn block brand" :disabled="loadingReceipt" @click="showReceipt = true">
          {{ loadingReceipt ? t('common.loading') : t('ret.choose') }}
        </button>
      </div>

      <div class="field-row">
        <div class="field">
          <label>{{ t('form.company') }}</label>
          <input :value="doc.company" disabled />
        </div>
        <div class="field">
          <label>{{ t('form.supplier') }}</label>
          <input :value="doc.supplier || '—'" disabled />
        </div>
      </div>

      <div class="field">
        <label>{{ t('form.date') }}</label>
        <input type="date" v-model="doc.date" />
      </div>
    </div>

    <div class="card mt12">
      <div class="row between">
        <div style="font-weight: 700">{{ t('ret.itemsToReturn') }} ({{ doc.items.length }})</div>
      </div>

      <div v-if="!doc.items.length" class="empty" style="padding: 26px">
        <div class="big"><Icon name="return" /></div>
        {{ t('ret.pickFirst') }}
      </div>

      <div v-for="line in doc.items" :key="line.item_code" class="item-line">
        <span class="thumb" style="display: grid; place-items: center; font-weight: 700; color: var(--muted)">
          {{ (line.item_name || '?').charAt(0).toUpperCase() }}
        </span>
        <div class="grow" style="min-width: 0">
          <div class="truncate" style="font-weight: 600">{{ line.item_name }}</div>
          <div class="tiny muted truncate">
            {{ line.item_code }} · {{ line.uom }} · {{ t('ret.returnable') }}: <b>{{ line.returnableQty }}</b>
          </div>
        </div>
        <div class="qty-box">
          <input
            type="number"
            inputmode="decimal"
            min="0"
            :max="line.returnableQty"
            :disabled="line.returnableQty <= 0"
            v-model.number="line.qty"
            @change="clampLine(line)"
          />
        </div>
      </div>

      <div v-if="doc.items.length" class="row between mt12" style="font-weight: 700">
        <span class="muted small">{{ t('ret.totalReturn') }}</span>
        <span>{{ totalQty }}</span>
      </div>
    </div>

    <div class="card mt12">
      <div style="font-weight: 700; margin-bottom: 10px">{{ t('form.photos') }}</div>
      <PhotoUploader v-model="doc.photos" :local-id="doc.localId" />
    </div>

    <div class="card mt12">
      <div class="field" style="margin: 0">
        <label>{{ t('common.note') }}</label>
        <textarea v-model="doc.remark" rows="2" :placeholder="t('ret.notePlaceholder')"></textarea>
      </div>
    </div>

    <div class="card mt12">
      <div class="row between">
        <div style="min-width: 0">
          <div style="font-weight: 700"><Icon name="location" /> {{ t('form.location') }}</div>
          <div v-if="doc.geo" class="tiny muted truncate">{{ doc.geo }}</div>
          <div v-else class="tiny muted">—</div>
        </div>
        <button class="btn sm" :class="doc.geo ? '' : 'brand'" :disabled="locating" @click="tagLocation">
          {{ locating ? t('form.locating') : t('form.tagLocation') }}
        </button>
      </div>
    </div>

    <div v-if="!app.online" class="banner-offline mt12">
      {{ blockedOffline ? t('form.onlineOnlyHint') : t('form.offlineHint') }}
    </div>

    <button class="btn brand block mt16" :disabled="saving || blockedOffline" @click="save">
      {{ saving ? t('common.saving') : blockedOffline ? t('form.onlineOnlyBtn') : app.online ? t('form.saveSync') : t('form.saveOutbox') }}
    </button>
    <div style="height: 8px"></div>

    <ReceiptSheet v-if="showReceipt" :company="doc.company" :supplier="doc.supplier" @pick="selectReceipt" @close="showReceipt = false" />
  </div>
</template>

<style scoped>
.po-chip {
  display: inline-flex; align-items: center; gap: 6px; min-width: 0; padding: 9px 12px;
  border-radius: 10px; background: var(--brand-soft, var(--line)); color: var(--ink);
  font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
</style>
