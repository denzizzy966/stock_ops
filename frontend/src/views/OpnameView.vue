<script setup>
import { ref, computed, onMounted } from 'vue'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { getOpnameSheet, createOpname } from '../lib/service'
import { uuid } from '../lib/util'
import AppBar from '../components/AppBar.vue'
import SearchInput from '../components/SearchInput.vue'
import FilterBar from '../components/FilterBar.vue'

const app = useApp()
const master = useMaster()
const { t } = useI18n()

// Perusahaan dari server (Employee/Settings) bila ada; jika tidak, default lokal.
const company = computed(() => (master.defaults && master.defaults.company) || app.settings.company)
const whOptions = computed(() =>
  master.userWarehouses.length ? master.userWarehouses : master.warehousesForCompany(company.value)
)
const warehouse = ref('')
const rows = ref([])
const q = ref('')
const loading = ref(false)
const saving = ref(false)

const filtered = computed(() => {
  const s = q.value.trim().toLowerCase()
  if (!s) return rows.value
  return rows.value.filter((r) => (r.item_name || '').toLowerCase().includes(s) || (r.item_code || '').toLowerCase().includes(s))
})
const changed = computed(() => rows.value.filter((r) => Number(r.counted) !== Number(r.system)))

async function load() {
  if (!warehouse.value) return
  loading.value = true
  try {
    const res = await getOpnameSheet(warehouse.value, company.value)
    rows.value = (res.items || []).map((i) => ({
      item_code: i.item_code,
      item_name: i.item_name,
      stock_uom: i.stock_uom,
      valuation_rate: i.valuation_rate,
      system: i.actual_qty,
      counted: i.actual_qty
    }))
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
    rows.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  warehouse.value = whOptions.value[0] || ''
  load()
})

function selectWh(w) {
  warehouse.value = w
  load()
}

async function submit() {
  if (!changed.value.length) return app.notify(t('opname.noDiff'), 'warn')
  saving.value = true
  try {
    const items = changed.value.map((r) => ({ item_code: r.item_code, qty: Number(r.counted), valuation_rate: r.valuation_rate }))
    const res = await createOpname(warehouse.value, items, company.value, uuid())
    app.notify(t('opname.created', { name: res.name, n: res.count || items.length }), 'success')
    await load()
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  } finally {
    saving.value = false
  }
}
function fmt(n) {
  return Number(n || 0).toLocaleString()
}
</script>

<template>
  <AppBar :title="t('opname.title')" back />
  <div class="content" style="padding-bottom: 90px">
    <FilterBar :collapsible="whOptions.length > 1">
      <template #bar><SearchInput v-model="q" :placeholder="t('opname.search')" /></template>
      <div v-if="whOptions.length > 1" class="chips wrap" style="margin-top: 10px">
        <button v-for="w in whOptions" :key="w" class="chip" :class="{ active: warehouse === w }" @click="selectWh(w)">{{ w }}</button>
      </div>
      <div v-else class="tiny muted" style="margin-top: 8px"><Icon name="warehouse" /> {{ warehouse }}</div>
    </FilterBar>

    <div v-if="loading">
      <div class="card" v-for="i in 4" :key="i" style="margin-top: 10px"><div class="skel skel-line" style="width: 55%"></div><div class="skel skel-line" style="width: 30%"></div></div>
    </div>
    <div v-else-if="!rows.length" class="empty"><div class="big"><Icon name="list" /></div>{{ t('opname.empty') }}</div>

    <div v-else class="card" style="padding: 4px 14px">
      <div v-for="r in filtered" :key="r.item_code" class="item-line">
        <div class="grow" style="min-width: 0">
          <div class="truncate" style="font-weight: 600">{{ r.item_name }}</div>
          <div class="tiny muted truncate">{{ r.item_code }} · {{ t('opname.system') }}: {{ fmt(r.system) }} {{ r.stock_uom }}</div>
          <div v-if="Number(r.counted) !== Number(r.system)" class="tiny" :style="{ color: Number(r.counted) > Number(r.system) ? 'var(--ok)' : 'var(--danger)', fontWeight: 700 }">
            {{ t('opname.diff') }}: {{ Number(r.counted) - Number(r.system) > 0 ? '+' : '' }}{{ fmt(Number(r.counted) - Number(r.system)) }}
          </div>
        </div>
        <div>
          <div class="tiny muted" style="text-align: center">{{ t('opname.counted') }}</div>
          <input
            type="number"
            inputmode="decimal"
            v-model.number="r.counted"
            :style="{ width: '76px', textAlign: 'center', border: '1px solid var(--line)', background: 'var(--input-bg)', color: 'var(--ink)', borderRadius: '10px', padding: '8px 6px', outline: Number(r.counted) !== Number(r.system) ? '2px solid var(--warn)' : 'none' }"
          />
        </div>
      </div>
    </div>
  </div>

  <!-- bar submit melayang -->
  <div v-if="rows.length" style="position: fixed; left: 50%; transform: translateX(-50%); bottom: calc(var(--tabbar-h) + var(--safe-bottom) + 10px); width: 100%; max-width: 520px; padding: 0 14px; z-index: 25">
    <button class="btn brand block" :disabled="saving || !changed.length" @click="submit" style="box-shadow: var(--shadow)">
      <Icon name="check-circle" /> {{ saving ? '…' : t('opname.submit') }} <span v-if="changed.length">· {{ changed.length }} {{ t('opname.count') }}</span>
    </button>
  </div>
</template>
