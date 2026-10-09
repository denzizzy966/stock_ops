<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useI18n } from '../lib/i18n'
import { getLowStock, bulkPurchaseRequest } from '../lib/service'
import { uuid } from '../lib/util'
import AppBar from '../components/AppBar.vue'
import FilterBar from '../components/FilterBar.vue'

const app = useApp()
const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const items = ref([])
const restricted = ref(false)
const warehouses = ref([])
const threshold = ref(10)
const sel = ref({}) // key -> true
let timer = null

const keyOf = (b) => b.item_code + '|' + b.warehouse
// Saran qty beli: pakai reorder_qty item (jika diset di child reorder_levels), jika tidak pakai kekurangan ke batas.
const suggest = (b) => (Number(b.reorder_qty) > 0 ? Math.round(b.reorder_qty) : Math.max(1, Math.ceil((b.limit || 0) - (b.actual_qty || 0))))
const selCount = computed(() => Object.values(sel.value).filter(Boolean).length)
const allSelected = computed(() => items.value.length > 0 && selCount.value === items.value.length)

async function load() {
  loading.value = true
  try {
    const res = await getLowStock(app.settings.company, threshold.value || 0)
    items.value = res.items || []
    restricted.value = !!res.restricted
    warehouses.value = res.warehouses || []
    sel.value = {}
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
    items.value = []
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(threshold, () => {
  clearTimeout(timer)
  timer = setTimeout(load, 400)
})

function toggle(k) {
  sel.value = { ...sel.value, [k]: !sel.value[k] }
}
function toggleAll() {
  if (allSelected.value) {
    sel.value = {}
  } else {
    const o = {}
    items.value.forEach((b) => (o[keyOf(b)] = true))
    sel.value = o
  }
}

async function bulkRequest() {
  const chosen = items.value.filter((b) => sel.value[keyOf(b)])
  if (!chosen.length) return
  saving.value = true
  try {
    const payload = chosen.map((b) => ({ item_code: b.item_code, qty: suggest(b), uom: b.stock_uom, warehouse: b.warehouse }))
    const res = await bulkPurchaseRequest(payload, app.settings.company, uuid())
    app.notify(t('low.created', { name: res.name, n: res.count || payload.length }), 'success')
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
  <AppBar :title="t('low.title')" back />
  <div class="content" :style="selCount ? 'padding-bottom: 96px' : ''">
    <FilterBar>
      <template #bar>
        <button v-if="items.length" class="btn sm" @click="toggleAll">{{ allSelected ? t('low.clear') : t('low.selectAll') }}</button>
        <span v-else class="tiny muted">{{ t('low.title') }}</span>
      </template>
      <div class="row" style="gap: 10px; align-items: center; margin-top: 10px">
        <label class="tiny muted" style="font-weight: 600">{{ t('low.threshold') }}</label>
        <input type="number" inputmode="numeric" v-model.number="threshold" style="width: 90px; border: 1px solid var(--line); background: var(--input-bg); color: var(--ink); border-radius: 10px; padding: 9px 12px" />
      </div>
    </FilterBar>

    <div v-if="restricted" class="tiny muted" style="margin: 6px 4px"><Icon name="lock" /> {{ t('balance.restricted') }}: {{ warehouses.join(', ') }}</div>

    <div v-if="loading">
      <div class="card" v-for="i in 4" :key="i" style="margin-top: 10px"><div class="skel skel-line" style="width: 55%"></div><div class="skel skel-line" style="width: 30%"></div></div>
    </div>
    <div v-else-if="!items.length" class="empty"><div class="big"><Icon name="check-circle" /></div>{{ t('low.empty') }}</div>

    <div v-else>
      <div
        v-for="b in items"
        :key="keyOf(b)"
        class="list-item mt12"
        :style="sel[keyOf(b)] ? 'outline: 2px solid var(--brand); outline-offset: -2px' : ''"
      >
        <span class="lead-icon" :style="{ background: b.actual_qty <= 0 ? 'var(--danger)' : 'var(--warn)' }"><Icon name="warning" /></span>
        <div class="grow" style="min-width: 0; cursor: pointer" @click="router.push(`/item/${encodeURIComponent(b.item_code)}`)">
          <div class="truncate" style="font-weight: 600">{{ b.item_name }}</div>
          <div class="tiny muted truncate">{{ b.item_code }} · <Icon name="warehouse" /> {{ b.warehouse }}</div>
          <div class="tiny muted">{{ t('low.level') }}: {{ fmt(b.limit) }} · {{ t('low.reqQty') }} <b style="color: var(--brand)">{{ fmt(suggest(b)) }}</b> {{ b.stock_uom }}</div>
        </div>
        <div style="text-align: right; margin-right: 4px">
          <div style="font-weight: 800; color: var(--danger)">{{ fmt(b.actual_qty) }}</div>
        </div>
        <input type="checkbox" :checked="!!sel[keyOf(b)]" @change="toggle(keyOf(b))" style="width: 22px; height: 22px; flex: none" />
      </div>
    </div>
  </div>

  <!-- bar bulk request melayang -->
  <div v-if="selCount" style="position: fixed; left: 50%; transform: translateX(-50%); bottom: calc(var(--tabbar-h) + var(--safe-bottom) + 10px); width: 100%; max-width: 520px; padding: 0 14px; z-index: 25">
    <button class="btn brand block" :disabled="saving" @click="bulkRequest" style="box-shadow: var(--shadow)">
      <Icon name="cart" /> {{ saving ? '…' : t('low.bulkRequest') }} · {{ t('low.selected', { n: selCount }) }}
    </button>
  </div>
</template>
