<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DOC_TYPES } from '../data/mock'
import { useApp } from '../stores/app'
import { useDocs } from '../stores/docs'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { getGeolocation } from '../lib/util'
import AppBar from '../components/AppBar.vue'
import ItemPickerSheet from '../components/ItemPickerSheet.vue'
import PhotoUploader from '../components/PhotoUploader.vue'
import SearchSelect from '../components/SearchSelect.vue'
import PurchaseOrderSheet from '../components/PurchaseOrderSheet.vue'
import { getPurchaseOrderItems } from '../lib/service'

const route = useRoute()
const router = useRouter()
const app = useApp()
const docs = useDocs()
const master = useMaster()
const { t } = useI18n()

const COMPANIES = computed(() => master.companyNames)
const SUPPLIERS = computed(() => master.supplierNames)
const CUSTOMERS = computed(() => master.customerNames)
const LOCATIONS = computed(() => master.locationNames)
// Company dikunci bila berasal dari Employee user (server). Lihat get_user_context.
const companyReadOnly = computed(() => !!(master.defaults && master.defaults.company_read_only))

const typeKey = route.params.type
const cfg = DOC_TYPES[typeKey]
if (!cfg) router.replace('/create')

const doc = reactive(docs.newDraft(typeKey))

// Gudang difilter sesuai company (hindari error warehouse↔company di MR).
const warehouseOptions = computed(() => master.warehousesForCompany(doc.company))
watch(
  () => doc.company,
  () => {
    const opts = warehouseOptions.value
    if (doc.sourceWarehouse && !opts.includes(doc.sourceWarehouse)) doc.sourceWarehouse = opts[0] || ''
    if (doc.targetWarehouse && !opts.includes(doc.targetWarehouse))
      doc.targetWarehouse = opts[Math.min(1, opts.length - 1)] || ''
  }
)
// Stock Out: Tujuan → cost center (Stock Ops Settings), disaring per perusahaan dokumen.
const purposeOptions = computed(() => (master.issuePurposes || []).filter((p) => p.company === doc.company))
const showPurpose = computed(() => cfg && cfg.key === 'SE_OUT' && purposeOptions.value.length > 0)
const purposeNames = computed(() => purposeOptions.value.map((p) => p.purpose))
const purposeCostCenter = computed(() => {
  const p = purposeOptions.value.find((o) => o.purpose === doc.purpose)
  return p ? p.cost_center : ''
})
watch(purposeOptions, (opts) => {
  if (doc.purpose && !opts.some((o) => o.purpose === doc.purpose)) doc.purpose = ''
})
const showPicker = ref(false)
const showPO = ref(false)
const loadingPO = ref(false)
const saving = ref(false)
const locating = ref(false)

// GRN (Purchase Receipt): tampilkan gudang-tolak bila ada qty ditolak, lokasi aset bila ada item aset.
const hasRejected = computed(() => doc.items.some((i) => Number(i.rejectedQty) > 0))
const hasAsset = computed(() => doc.items.some((i) => i.is_fixed_asset))
// Stock Entry / Penerimaan / Retur wajib online — tak bisa dibuat offline (hanya MR yang boleh).
const blockedOffline = computed(() => !!(cfg && cfg.onlineOnly && !app.online))
// Gudang acuan stok di item picker: gudang asal bila ada (keluar/transfer), selain itu tujuan.
const pickerWarehouse = computed(() => (cfg && cfg.source ? doc.sourceWarehouse : doc.targetWarehouse) || '')

// ===== Peringatan stok (lunak) untuk dokumen yang MENGURANGI stok (ada gudang asal) =====
// Angka stok diambil dari saldo gudang asal (cache master.stockByWh). Peringatan bersifat
// lunak: submit tetap boleh — ERPNext yang menentukan sesuai setting Allow Negative Stock.
const stockCheckWh = computed(() => (cfg && cfg.source ? doc.sourceWarehouse : '') || '')
watch(
  stockCheckWh,
  (wh) => {
    if (wh) master.loadWarehouseStock(wh)
  },
  { immediate: true }
)
const round2 = (n) => Math.round((Number(n) || 0) * 100) / 100
function stockUomOf(line) {
  const it = master.itemList.find((x) => x.item_code === line.item_code)
  return (it && it.stock_uom) || line.uom || ''
}
// Stok tersedia (dalam stock_uom) di gudang asal; null bila belum dimuat / tak ada gudang.
function availableStock(line) {
  const wh = stockCheckWh.value
  if (!wh) return null
  const m = master.stockByWh[wh]
  if (!m) return null
  return round2(m[line.item_code] || 0)
}
// Qty dibutuhkan dalam stock_uom = qty × faktor konversi UOM.
function neededStockQty(line) {
  return round2((Number(line.qty) || 0) * (Number(line.conversionFactor) || 1))
}
function isShort(line) {
  const avail = availableStock(line)
  if (avail === null) return false
  return neededStockQty(line) > avail + 1e-9
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

const totalQty = computed(() => doc.items.reduce((s, i) => s + (Number(i.qty) || 0), 0))

function addItem(it) {
  const exist = doc.items.find((x) => x.item_code === it.item_code)
  if (exist) exist.qty += 1
  else
    doc.items.push({ item_code: it.item_code, item_name: it.item_name, image: it.image, uom: it.stock_uom, conversionFactor: 1, qty: 1, rejectedQty: 0, is_fixed_asset: it.is_fixed_asset ? 1 : 0 })
  showPicker.value = false
}

// UOM yang bisa dipilih untuk item (selalu >=1: stock_uom + konversi tambahan dari master item).
// Dropdown SELALU tampil (bukan karena stok) — item tanpa konversi hanya punya 1 opsi (stock_uom).
function itemUoms(line) {
  const it = master.itemList.find((x) => x.item_code === line.item_code)
  if (it && it.uoms && it.uoms.length) return it.uoms
  return [{ uom: line.uom, conversion_factor: 1 }]
}
function setUom(line, uom) {
  line.uom = uom
  line.conversionFactor = uomFactor(line.item_code, uom)
}
function uomFactor(code, uom) {
  const it = master.itemList.find((x) => x.item_code === code)
  const u = it && it.uoms && it.uoms.find((o) => o.uom === uom)
  return u ? u.conversion_factor : 1
}

// Penerimaan Barang: pilih PO → tarik item PO yang belum diterima (auto-isi + link).
async function selectPO(po) {
  showPO.value = false
  loadingPO.value = true
  try {
    const res = await getPurchaseOrderItems(po.name)
    doc.purchaseOrder = res.name
    if (res.company) doc.company = res.company // receipt harus seperusahaan dengan PO
    if (res.supplier) doc.supplier = res.supplier
    if (res.set_warehouse) doc.targetWarehouse = res.set_warehouse
    doc.items = (res.items || []).map((i) => ({
      item_code: i.item_code,
      item_name: i.item_name,
      uom: i.uom,
      conversionFactor: uomFactor(i.item_code, i.uom),
      qty: Number(i.qty) || 0,
      rejectedQty: 0,
      rate: i.rate,
      is_fixed_asset: i.is_fixed_asset ? 1 : 0,
      purchase_order: i.purchase_order,
      purchase_order_item: i.purchase_order_item
    }))
    app.notify(t('po.loaded', { n: doc.items.length, po: res.name }), 'success')
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  } finally {
    loadingPO.value = false
  }
}
function clearPO() {
  doc.purchaseOrder = ''
  doc.items.forEach((i) => {
    delete i.purchase_order
    delete i.purchase_order_item
  })
}

// Prefill item bila dibuka dari Detail Item (?item=CODE)
if (route.query.item) {
  const it = master.itemList.find((x) => x.item_code === route.query.item)
  if (it) addItem(it)
}
function step(line, d) {
  line.qty = Math.max(0, (Number(line.qty) || 0) + d)
}
function removeLine(code) {
  doc.items = doc.items.filter((i) => i.item_code !== code)
}

function valid() {
  if (!doc.items.length) return t('form.vItems')
  if (cfg.acceptReject) {
    // GRN: tiap baris harus punya (terima + tolak) > 0
    if (doc.items.some((i) => (Number(i.qty) || 0) + (Number(i.rejectedQty) || 0) <= 0)) return t('form.vQty')
    if (hasRejected.value && !doc.rejectedWarehouse) return t('form.vRejWh')
    if (hasAsset.value && !doc.assetLocation) return t('form.vAssetLoc')
  } else if (doc.items.some((i) => !i.qty || i.qty <= 0)) {
    return t('form.vQty')
  }
  if (cfg.supplierRequired && !doc.supplier) return t('form.vSupplier')
  if (cfg.customer && !(doc.customer && doc.customer.trim())) return t('form.vCustomer')
  if (cfg.source && !doc.sourceWarehouse) return t('form.vSrc')
  if (cfg.target && !doc.targetWarehouse) return t('form.vTgt')
  if (cfg.source && cfg.target && doc.sourceWarehouse === doc.targetWarehouse) return t('form.vSame')
  if (showPurpose.value && master.issuePurposeRequired && !doc.purpose) return t('form.vPurpose')
  return null
}

async function save() {
  const err = valid()
  if (err) return app.notify(err, 'warn')
  if (blockedOffline.value) return app.notify(t('form.onlineOnly', { doc: t('docType.' + cfg.key) }), 'error')
  saving.value = true
  const saved = await docs.save({ ...doc })
  saving.value = false
  if (saved) router.replace(`/doc/${doc.localId}`)
}
</script>

<template>
  <AppBar :title="cfg ? t('docType.' + cfg.key) + ' · ' + t('form.newSuffix') : ''" back />
  <div class="content" v-if="cfg">
    <div class="card">
      <div class="row" style="gap: 10px; margin-bottom: 12px">
        <span class="lead-icon" :style="{ background: cfg.color }"><Icon :name="cfg.icon" /></span>
        <div class="grow">
          <div style="font-weight: 700">{{ t('docType.' + cfg.key) }}</div>
          <div class="tiny muted">{{ cfg.doctype }}</div>
        </div>
      </div>

      <div class="field">
        <label>{{ t('form.company') }}</label>
        <SearchSelect v-model="doc.company" :options="COMPANIES" :disabled="companyReadOnly" :placeholder="t('form.company')" />
        <div v-if="companyReadOnly" class="tiny muted" style="margin-top: 4px">{{ t('form.companyFromAccount') }}</div>
      </div>

      <div class="field">
        <label>{{ t('form.date') }}</label>
        <input type="date" v-model="doc.date" />
      </div>

      <div v-if="cfg.purchaseOrder" class="field">
        <label>{{ t('po.label') }} <span class="muted">({{ t('common.optional') }})</span></label>
        <div v-if="doc.purchaseOrder" class="row between" style="gap: 8px; align-items: center">
          <span class="po-chip"><Icon name="receipt" /> {{ doc.purchaseOrder }}</span>
          <button class="btn sm" @click="clearPO">{{ t('common.clear') }}</button>
        </div>
        <button v-else class="btn block" :disabled="loadingPO" @click="showPO = true">
          {{ loadingPO ? t('common.loading') : t('po.choose') }}
        </button>
      </div>

      <div v-if="cfg.supplier" class="field">
        <label>{{ t('form.supplier') }}<span v-if="!cfg.supplierRequired"> ({{ t('common.optional') }})</span></label>
        <SearchSelect v-model="doc.supplier" :options="SUPPLIERS" :disabled="!!doc.purchaseOrder" clearable :placeholder="t('form.supplier')" />
      </div>

      <div v-if="cfg.customer" class="field">
        <label>{{ t('form.customer') }}</label>
        <input list="stockops-customers" v-model="doc.customer" :placeholder="t('form.customerPlaceholder')" autocomplete="off" />
        <datalist id="stockops-customers">
          <option v-for="c in CUSTOMERS" :key="c" :value="c" />
        </datalist>
        <div class="tiny muted" style="margin-top: 4px">{{ t('form.customerHint') }}</div>
      </div>

      <div class="field-row">
        <div v-if="cfg.source" class="field">
          <label>{{ t('form.sourceWh') }}</label>
          <SearchSelect :search-placeholder="t('form.whSearch')" :empty-text="t('form.whEmpty')" v-model="doc.sourceWarehouse" :options="warehouseOptions" :placeholder="t('form.sourceWh')" />
        </div>
        <div v-if="cfg.target" class="field">
          <label>{{ cfg.acceptReject ? t('form.acceptedWh') : t('form.targetWh') }}</label>
          <SearchSelect :search-placeholder="t('form.whSearch')" :empty-text="t('form.whEmpty')" v-model="doc.targetWarehouse" :options="warehouseOptions" :placeholder="cfg.acceptReject ? t('form.acceptedWh') : t('form.targetWh')" />
        </div>
      </div>

      <div v-if="showPurpose" class="field">
        <label>{{ t('form.purpose') }}<span v-if="!master.issuePurposeRequired"> ({{ t('common.optional') }})</span></label>
        <SearchSelect v-model="doc.purpose" :options="purposeNames" clearable :placeholder="t('form.purpose')" />
        <div v-if="purposeCostCenter" class="tiny muted" style="margin-top: 4px">{{ t('form.costCenter') }}: {{ purposeCostCenter }}</div>
      </div>

      <div v-if="cfg.acceptReject && hasRejected" class="field">
        <label>{{ t('form.rejectedWh') }}</label>
        <SearchSelect :search-placeholder="t('form.whSearch')" :empty-text="t('form.whEmpty')" v-model="doc.rejectedWarehouse" :options="warehouseOptions" :placeholder="t('form.rejectedWh')" />
      </div>
      <div v-if="cfg.acceptReject && hasAsset" class="field">
        <label>{{ t('form.assetLocation') }}</label>
        <SearchSelect v-model="doc.assetLocation" :options="LOCATIONS" :placeholder="t('form.assetLocation')" />
      </div>
    </div>

    <div class="card mt12">
      <div class="row between">
        <div style="font-weight: 700">{{ t('common.items') }} ({{ doc.items.length }})</div>
        <button class="btn brand sm" @click="showPicker = true"><Icon name="plus" /> {{ t('common.add') }}</button>
      </div>

      <div v-if="!doc.items.length" class="empty" style="padding: 26px">
        <div class="big"><Icon name="basket" /></div>
        {{ t('form.noItems') }}
      </div>

      <div v-for="line in doc.items" :key="line.item_code" class="item-line">
        <img v-if="line.image" :src="line.image" class="thumb" alt="" />
        <span v-else class="thumb" style="display: grid; place-items: center; font-weight: 700; color: var(--muted)">
          {{ (line.item_name || '?').charAt(0).toUpperCase() }}
        </span>
        <div class="grow" style="min-width: 0">
          <div class="truncate" style="font-weight: 600">
            {{ line.item_name }}
            <span v-if="line.is_fixed_asset" class="asset-tag">{{ t('form.asset') }}</span>
          </div>
          <div class="tiny muted truncate">
            {{ line.item_code }}<span v-if="line.purchase_order"> · {{ line.purchase_order }}</span>
          </div>
          <div class="uom-row">
            <span class="uom-lbl">{{ t('form.uom') }}</span>
            <SearchSelect compact :model-value="line.uom" :options="itemUoms(line).map((u) => u.uom)" @update:model-value="(v) => setUom(line, v)" />
          </div>
          <div v-if="isShort(line)" class="stock-warn">
            <Icon name="warning" /> {{ t('form.insufficientStock', { need: neededStockQty(line), avail: availableStock(line), uom: stockUomOf(line) }) }}
          </div>
          <div v-if="cfg.acceptReject" class="row" style="gap: 12px; margin-top: 8px; align-items: center">
            <label class="tiny muted" style="display: flex; align-items: center; gap: 5px">{{ t('form.accepted') }}
              <input type="number" inputmode="decimal" min="0" v-model.number="line.qty" class="mini-num" />
            </label>
            <label class="tiny muted" style="display: flex; align-items: center; gap: 5px">{{ t('form.rejected') }}
              <input type="number" inputmode="decimal" min="0" v-model.number="line.rejectedQty" class="mini-num" />
            </label>
          </div>
        </div>
        <div v-if="!cfg.acceptReject" class="qty-box">
          <button @click="step(line, -1)">−</button>
          <input type="number" inputmode="decimal" v-model.number="line.qty" />
          <button @click="step(line, 1)"><Icon name="plus" /></button>
        </div>
        <button class="btn sm danger" style="padding: 8px 10px; align-self: flex-start" @click="removeLine(line.item_code)"><Icon name="trash" /></button>
      </div>

      <div v-if="doc.items.length" class="row between mt12" style="font-weight: 700">
        <span class="muted small">{{ t('form.totalQty') }}</span>
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
        <textarea v-model="doc.remark" rows="2" :placeholder="t('form.notePlaceholder')"></textarea>
      </div>
    </div>

    <div class="card mt12">
      <div class="row between">
        <div style="min-width: 0">
          <div style="font-weight: 700"><Icon name="location" /> {{ t('form.location') }}</div>
          <div v-if="doc.geo" class="tiny muted truncate">
            {{ doc.geo }} ·
            <a :href="`https://maps.google.com/?q=${doc.geo}`" target="_blank" style="color: var(--brand)">{{ t('form.viewMap') }}</a>
          </div>
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

    <ItemPickerSheet v-if="showPicker" :warehouse="pickerWarehouse" @pick="addItem" @close="showPicker = false" />
    <PurchaseOrderSheet v-if="showPO" :company="doc.company" :supplier="doc.supplier" @pick="selectPO" @close="showPO = false" />
  </div>
</template>

<style scoped>
.mini-num {
  width: 64px; border: 1px solid var(--line); border-radius: 8px; padding: 6px 8px;
  background: var(--input-bg); color: var(--ink); text-align: center; font-size: 15px;
}
.po-chip {
  display: inline-flex; align-items: center; gap: 6px; min-width: 0; padding: 9px 12px;
  border-radius: 10px; background: var(--brand-soft, var(--line)); color: var(--ink);
  font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.asset-tag {
  font-size: 10px; background: #0891b2; color: #fff; padding: 1px 7px; border-radius: 999px; margin-left: 4px; font-weight: 700;
}
.uom-row {
  display: flex; align-items: center; gap: 8px; margin-top: 8px;
}
.uom-lbl { font-size: 12px; color: var(--muted); font-weight: 600; }
.stock-warn {
  margin-top: 7px; font-size: 12px; font-weight: 700; line-height: 1.35;
  color: #92400e; background: #fef3c7; border: 1px solid #fcd34d;
  padding: 5px 9px; border-radius: 8px;
}
</style>
