<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useI18n } from '../lib/i18n'
import { getStockBalance } from '../lib/service'
import AppBar from '../components/AppBar.vue'
import SearchInput from '../components/SearchInput.vue'
import FilterBar from '../components/FilterBar.vue'

const app = useApp()
const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const balance = ref([])
const warehouses = ref([])
const restricted = ref(false)
const q = ref('')
const whFilter = ref('ALL')

async function load() {
  loading.value = true
  try {
    const res = await getStockBalance({ company: app.settings.company })
    balance.value = res.balance || []
    warehouses.value = res.warehouses || []
    restricted.value = !!res.restricted
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
    balance.value = []
  } finally {
    loading.value = false
  }
}
onMounted(load)

const filtered = computed(() => {
  const s = q.value.trim().toLowerCase()
  return balance.value.filter((b) => {
    if (whFilter.value !== 'ALL' && b.warehouse !== whFilter.value) return false
    if (!s) return true
    return (b.item_name || '').toLowerCase().includes(s) || (b.item_code || '').toLowerCase().includes(s)
  })
})

// kelompokkan per gudang
const grouped = computed(() => {
  const m = {}
  for (const b of filtered.value) {
    ;(m[b.warehouse] = m[b.warehouse] || []).push(b)
  }
  return Object.keys(m)
    .sort()
    .map((w) => ({
      warehouse: w,
      items: m[w],
      total: m[w].reduce((s, x) => s + (x.actual_qty || 0), 0),
      max: Math.max(1, ...m[w].map((x) => x.actual_qty || 0))
    }))
})

function fmt(n) {
  return Number(n || 0).toLocaleString()
}
</script>

<template>
  <AppBar :title="t('balance.title')" back />
  <div class="content">
    <FilterBar :collapsible="warehouses.length > 1" :count="whFilter !== 'ALL' ? 1 : 0">
      <template #bar>
        <div class="row" style="gap: 8px">
          <SearchInput v-model="q" :placeholder="t('balance.search')" class="grow" />
          <button class="btn sm" :disabled="loading" @click="load"><Icon name="refresh" /></button>
        </div>
      </template>
      <div v-if="warehouses.length > 1" class="chips wrap" style="margin-top: 10px">
        <button class="chip" :class="{ active: whFilter === 'ALL' }" @click="whFilter = 'ALL'">{{ t('balance.allWh') }}</button>
        <button v-for="w in warehouses" :key="w" class="chip" :class="{ active: whFilter === w }" @click="whFilter = w">{{ w }}</button>
      </div>
    </FilterBar>

    <div v-if="restricted" class="tiny muted" style="margin: 6px 4px"><Icon name="lock" /> {{ t('balance.restricted') }}: {{ warehouses.join(', ') }}</div>

    <div v-if="loading">
      <div class="card" v-for="i in 4" :key="i" style="margin-top: 10px">
        <div class="skel skel-line" style="width: 55%"></div>
        <div class="skel skel-line" style="width: 30%"></div>
      </div>
    </div>
    <div v-else-if="!grouped.length" class="empty"><div class="big"><Icon name="box" /></div>{{ t('balance.empty') }}</div>

    <template v-else>
      <div v-for="g in grouped" :key="g.warehouse">
        <div class="section-title"><Icon name="warehouse" /> {{ g.warehouse }} · {{ g.items.length }} {{ t('balance.items') }}</div>
        <div class="card" style="padding: 4px 14px">
          <div
            v-for="b in g.items"
            :key="b.item_code + b.warehouse"
            class="item-line"
            style="cursor: pointer"
            @click="router.push(`/item/${encodeURIComponent(b.item_code)}`)"
          >
            <div class="grow" style="min-width: 0">
              <div class="truncate" style="font-weight: 600">{{ b.item_name }}</div>
              <div class="tiny muted truncate">
                {{ b.item_code }}<span v-if="b.reserved_qty"> · {{ t('balance.reserved') }} {{ fmt(b.reserved_qty) }}</span>
              </div>
              <div class="qbar"><i :style="{ width: Math.min(100, (b.actual_qty / g.max) * 100) + '%', background: b.actual_qty <= 0 ? 'var(--danger)' : 'var(--brand)' }"></i></div>
            </div>
            <div style="text-align: right">
              <div style="font-weight: 800; font-size: 17px">{{ fmt(b.actual_qty) }}</div>
              <div class="tiny muted">{{ b.stock_uom }}</div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
