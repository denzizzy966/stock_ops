<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useApp } from '../stores/app'
import { useI18n } from '../lib/i18n'
import { getStockLedger } from '../lib/service'
import AppBar from '../components/AppBar.vue'
import SearchInput from '../components/SearchInput.vue'
import FilterBar from '../components/FilterBar.vue'
import { fmtDateTime } from '../lib/util'

const app = useApp()
const { t } = useI18n()

const loading = ref(false)
const entries = ref([])
const warehouses = ref([])
const restricted = ref(false)
const q = ref('')
const direction = ref('all') // all | in | out
const whFilter = ref('ALL')
const fromDate = ref('')
const toDate = ref('')

async function load() {
  loading.value = true
  try {
    const res = await getStockLedger({
      company: app.settings.company,
      direction: direction.value === 'all' ? '' : direction.value,
      warehouse: whFilter.value === 'ALL' ? '' : whFilter.value,
      from_date: fromDate.value || '',
      to_date: toDate.value || '',
      limit: 150
    })
    entries.value = res.entries || []
    warehouses.value = res.warehouses || []
    restricted.value = !!res.restricted
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
    entries.value = []
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch([direction, whFilter, fromDate, toDate], load)
function clearDates() {
  fromDate.value = ''
  toDate.value = ''
}
const activeCount = computed(
  () => (direction.value !== 'all' ? 1 : 0) + (whFilter.value !== 'ALL' ? 1 : 0) + (fromDate.value ? 1 : 0) + (toDate.value ? 1 : 0)
)

const filtered = computed(() => {
  const s = q.value.trim().toLowerCase()
  if (!s) return entries.value
  return entries.value.filter(
    (e) => (e.item_name || '').toLowerCase().includes(s) || (e.item_code || '').toLowerCase().includes(s)
  )
})

function fmt(n) {
  return Number(n || 0).toLocaleString()
}
function dt(e) {
  return fmtDateTime(`${String(e.posting_date).slice(0, 10)}T${(e.posting_time || '00:00:00').split('.')[0]}`)
}
</script>

<template>
  <AppBar :title="t('movement.title')" back />
  <div class="content">
    <FilterBar :count="activeCount">
      <template #bar><SearchInput v-model="q" :placeholder="t('movement.search')" /></template>
      <div class="seg" style="margin-top: 10px">
        <button :class="{ active: direction === 'all' }" @click="direction = 'all'">{{ t('movement.all') }}</button>
        <button :class="{ active: direction === 'in' }" @click="direction = 'in'">↓ {{ t('movement.in') }}</button>
        <button :class="{ active: direction === 'out' }" @click="direction = 'out'">↑ {{ t('movement.out') }}</button>
      </div>
      <div class="filter-dates" style="margin-top: 10px">
        <label class="date-field"><span>{{ t('movement.from') }}</span><input type="date" v-model="fromDate" /></label>
        <label class="date-field"><span>{{ t('movement.to') }}</span><input type="date" v-model="toDate" /></label>
        <button v-if="fromDate || toDate" class="btn sm" style="align-self: flex-end" @click="clearDates"><Icon name="close" /></button>
      </div>
      <div v-if="warehouses.length > 1" class="chips wrap" style="margin-top: 10px">
        <button class="chip" :class="{ active: whFilter === 'ALL' }" @click="whFilter = 'ALL'">{{ t('balance.allWh') }}</button>
        <button v-for="w in warehouses" :key="w" class="chip" :class="{ active: whFilter === w }" @click="whFilter = w">{{ w }}</button>
      </div>
    </FilterBar>

    <div v-if="restricted" class="tiny muted" style="margin: 6px 4px"><Icon name="lock" /> {{ t('balance.restricted') }}: {{ warehouses.join(', ') }}</div>

    <div v-if="loading">
      <div class="card" v-for="i in 4" :key="i" style="margin-top: 10px">
        <div class="skel skel-line" style="width: 60%"></div>
        <div class="skel skel-line" style="width: 35%"></div>
      </div>
    </div>
    <div v-else-if="!filtered.length" class="empty"><div class="big"><Icon name="movement" /></div>{{ t('movement.empty') }}</div>

    <div v-else class="card" style="margin-top: 8px; padding: 4px 14px">
      <div v-for="e in filtered" :key="e.name" class="move-row">
        <div class="grow" style="min-width: 0">
          <div class="truncate" style="font-weight: 600">{{ e.item_name }}</div>
          <div class="tiny muted truncate">
            <span class="move-badge">{{ e.voucher_type }}</span>
            {{ e.voucher_no }} · {{ dt(e) }}
          </div>
          <div class="tiny muted truncate"><Icon name="warehouse" /> {{ e.warehouse }}</div>
        </div>
        <div style="text-align: right">
          <div class="move-qty" :class="e.actual_qty >= 0 ? 'in' : 'out'">
            {{ e.actual_qty >= 0 ? '+' : '' }}{{ fmt(e.actual_qty) }}
          </div>
          <div class="tiny muted">{{ t('movement.sisa') }} {{ fmt(e.qty_after_transaction) }} {{ e.stock_uom }}</div>
        </div>
      </div>
    </div>
  </div>
</template>
