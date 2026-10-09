<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import Sheet from './Sheet.vue'
import BarcodeScanner from './BarcodeScanner.vue'
import SearchInput from './SearchInput.vue'

// `warehouse` = gudang yang dipilih di form → tampilkan stok tersedia per item di gudang itu.
const props = defineProps({ warehouse: { type: String, default: '' } })
const emit = defineEmits(['pick', 'close'])
const app = useApp()
const master = useMaster()
const { t } = useI18n()
const q = ref('')
const showScanner = ref(false)

const items = computed(() => master.itemList)

// Stok per item di gudang terpilih (dari cache master.stockByWh).
const loadingStock = ref(false)
async function loadStock() {
  if (!props.warehouse || !app.online) return
  loadingStock.value = true
  try {
    await master.loadWarehouseStock(props.warehouse)
  } finally {
    loadingStock.value = false
  }
}
onMounted(loadStock)
watch(() => props.warehouse, loadStock)
const stockMap = computed(() => (props.warehouse && master.stockByWh[props.warehouse]) || null)
function stockOf(it) {
  const v = Number((stockMap.value && stockMap.value[it.item_code]) || 0)
  return Number.isInteger(v) ? v : +v.toFixed(2)
}
const results = computed(() => {
  const s = q.value.trim().toLowerCase()
  if (!s) return items.value.slice(0, 100)
  return items.value
    .filter(
      (i) =>
        (i.item_name || '').toLowerCase().includes(s) ||
        (i.item_code || '').toLowerCase().includes(s) ||
        (i.barcode || '').includes(s)
    )
    .slice(0, 100)
})

function initials(it) {
  return (it.item_name || it.item_code || '?').trim().charAt(0).toUpperCase()
}

function onDetected(code) {
  showScanner.value = false
  const found = items.value.find((i) => i.barcode && i.barcode === code)
  if (found) {
    app.notify(t('toast.scan', { code, name: found.item_name }), 'success')
    emit('pick', found)
  } else {
    q.value = code // tampilkan hasil scan di pencarian untuk dicocokkan manual
    app.notify(t('scan.notFound', { code }), 'warn')
  }
}
</script>

<template>
  <Sheet :title="t('picker.title')" @close="emit('close')">
    <div class="row" style="gap: 8px; margin-bottom: 8px">
      <SearchInput v-model="q" :placeholder="t('picker.searchPlaceholder')" class="grow" />
      <button class="btn brand" style="padding: 12px 14px" @click="showScanner = true" :title="t('scan.title')"><Icon name="camera" /></button>
    </div>
    <div v-if="warehouse" class="tiny muted" style="margin: 0 4px 10px">
      {{ t('picker.stockAt', { wh: warehouse }) }}<span v-if="loadingStock"> · {{ t('common.loading') }}</span>
    </div>

    <div v-for="it in results" :key="it.item_code" class="list-item" @click="emit('pick', it)" style="cursor: pointer">
      <img v-if="it.image" :src="it.image" class="thumb" alt="" />
      <span v-else class="thumb" style="display: grid; place-items: center; font-weight: 700; color: var(--muted)">{{ initials(it) }}</span>
      <div class="grow" style="min-width: 0">
        <div class="truncate" style="font-weight: 600">{{ it.item_name }}</div>
        <div class="tiny muted truncate">{{ it.item_code }} · {{ it.stock_uom }}<span v-if="it.barcode"> · {{ it.barcode }}</span></div>
      </div>
      <span v-if="warehouse" class="stk-badge" :class="{ zero: stockOf(it) <= 0 }">
        {{ stockOf(it) }} <span class="tiny">{{ it.stock_uom }}</span>
      </span>
      <span style="font-size: 22px; color: var(--brand)"><Icon name="plus" /></span>
    </div>

    <div v-if="!results.length" class="empty">
      <div class="big"><Icon name="search" /></div>
      {{ t('picker.noMatch') }}
    </div>

    <BarcodeScanner v-if="showScanner" @detected="onDetected" @close="showScanner = false" />
  </Sheet>
</template>

<style scoped>
.stk-badge {
  flex-shrink: 0;
  padding: 3px 9px;
  border-radius: 999px;
  background: #dcfce7;
  color: #166534;
  font-weight: 700;
  font-size: 13px;
  white-space: nowrap;
}
.stk-badge.zero {
  background: var(--line);
  color: var(--muted);
}
.stk-badge .tiny {
  font-weight: 500;
  opacity: 0.8;
}
</style>
