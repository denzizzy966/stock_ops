<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useDocs } from '../stores/docs'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import AppBar from '../components/AppBar.vue'
import ItemPickerSheet from '../components/ItemPickerSheet.vue'
import SearchSelect from '../components/SearchSelect.vue'

const route = useRoute()
const router = useRouter()
const app = useApp()
const docs = useDocs()
const master = useMaster()
const { t } = useI18n()

// Perusahaan dari server (Employee/Settings) bila ada; jika tidak, default lokal.
const company = ref((master.defaults && master.defaults.company) || app.settings.company)
const warehouseOptions = computed(() => master.warehousesForCompany(company.value))

const form = reactive({
  item: null, // { item_code, item_name, stock_uom, image }
  from: app.settings.defaultSourceWarehouse || '',
  to: app.settings.defaultTargetWarehouse || '',
  qty: 1
})
const showPicker = ref(false)
const saving = ref(false)

onMounted(() => {
  const opts = warehouseOptions.value
  if (!opts.includes(form.from)) form.from = opts[0] || ''
  if (!opts.includes(form.to)) form.to = opts[Math.min(1, opts.length - 1)] || ''
  const code = route.query.item
  if (code) {
    const it = master.itemList.find((x) => x.item_code === code)
    if (it) form.item = { item_code: it.item_code, item_name: it.item_name, stock_uom: it.stock_uom, image: it.image }
  }
})

function pick(it) {
  form.item = { item_code: it.item_code, item_name: it.item_name, stock_uom: it.stock_uom, image: it.image }
  showPicker.value = false
}
function step(d) {
  form.qty = Math.max(0, (Number(form.qty) || 0) + d)
}

async function submit() {
  if (!form.item) return app.notify(t('qt.needItem'), 'warn')
  if (!form.qty || form.qty <= 0) return app.notify(t('qt.needQty'), 'warn')
  if (!form.from || !form.to || form.from === form.to) return app.notify(t('qt.sameWh'), 'warn')
  if (!app.online) return app.notify(t('form.onlineOnly', { doc: t('docType.SE_TRANSFER') }), 'error')
  saving.value = true
  const doc = docs.newDraft('SE_TRANSFER')
  doc.company = company.value
  doc.sourceWarehouse = form.from
  doc.targetWarehouse = form.to
  doc.items = [
    {
      item_code: form.item.item_code,
      item_name: form.item.item_name,
      image: form.item.image,
      uom: form.item.stock_uom,
      qty: Number(form.qty)
    }
  ]
  const saved = await docs.save({ ...doc })
  saving.value = false
  if (saved) router.replace(`/doc/${doc.localId}`)
}
</script>

<template>
  <AppBar :title="t('qt.title')" back />
  <div class="content">
    <div class="card">
      <!-- Item -->
      <div class="field">
        <label>{{ t('qt.item') }}</label>
        <button class="list-item" style="width: 100%; border: 0; cursor: pointer; box-shadow: none; background: var(--input-bg); border: 1px solid var(--line)" @click="showPicker = true">
          <template v-if="form.item">
            <img v-if="form.item.image" :src="form.item.image" class="thumb" alt="" />
            <span v-else class="thumb" style="display: grid; place-items: center; font-weight: 700; color: var(--muted)">{{ (form.item.item_name || '?').charAt(0) }}</span>
            <div class="grow"><div class="truncate" style="font-weight: 600">{{ form.item.item_name }}</div><div class="tiny muted">{{ form.item.item_code }}</div></div>
          </template>
          <div v-else class="grow muted">{{ t('qt.pickItem') }}</div>
          <span style="font-size: 20px; color: var(--muted)"><Icon name="search" /></span>
        </button>
      </div>

      <div class="field-row">
        <div class="field">
          <label>{{ t('qt.from') }}</label>
          <SearchSelect :search-placeholder="t('form.whSearch')" :empty-text="t('form.whEmpty')" v-model="form.from" :options="warehouseOptions" :placeholder="t('qt.from')" />
        </div>
        <div class="field">
          <label>{{ t('qt.to') }}</label>
          <SearchSelect :search-placeholder="t('form.whSearch')" :empty-text="t('form.whEmpty')" v-model="form.to" :options="warehouseOptions" :placeholder="t('qt.to')" />
        </div>
      </div>

      <div class="field" style="margin: 0">
        <label>{{ t('qt.qty') }}</label>
        <div class="qty-box" style="width: fit-content">
          <button @click="step(-1)">−</button>
          <input type="number" inputmode="decimal" v-model.number="form.qty" style="width: 80px" />
          <button @click="step(1)"><Icon name="plus" /></button>
        </div>
      </div>
    </div>

    <button class="btn brand block mt16" :disabled="saving" @click="submit">
      <Icon name="transfer" /> {{ saving ? '…' : t('qt.submit') }}
    </button>

    <ItemPickerSheet v-if="showPicker" :warehouse="form.from" @pick="pick" @close="showPicker = false" />
  </div>
</template>
