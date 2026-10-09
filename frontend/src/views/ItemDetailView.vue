<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { getItemDetail } from '../lib/service'
import AppBar from '../components/AppBar.vue'
import { fmtDateTime } from '../lib/util'

const route = useRoute()
const router = useRouter()
const app = useApp()
const master = useMaster()
const { t } = useI18n()

const loading = ref(false)
const data = ref(null)
const code = ref(route.params.code)

async function load() {
  loading.value = true
  try {
    data.value = await getItemDetail(code.value, app.settings.company)
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
    data.value = null
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(() => route.params.code, (c) => { code.value = c; load() })

function fmt(n) {
  return Number(n || 0).toLocaleString()
}
function dt(m) {
  return fmtDateTime(`${String(m.posting_date).slice(0, 10)}T${(m.posting_time || '00:00:00').split('.')[0]}`)
}
function quick(type) {
  if (type === 'SE_TRANSFER') return router.push({ path: '/quick-transfer', query: { item: code.value } })
  router.push({ path: `/form/${type}`, query: { item: code.value } })
}
function initials() {
  const it = data.value && data.value.item
  return ((it && (it.item_name || it.item_code)) || '?').trim().charAt(0).toUpperCase()
}
</script>

<template>
  <AppBar :title="t('item.title')" back />
  <div class="content">
    <div v-if="loading" class="card"><div class="skel skel-line" style="width: 60%"></div><div class="skel skel-line" style="width: 40%"></div></div>

    <template v-else-if="data">
      <!-- Header -->
      <div class="card">
        <div class="row idv-head" style="gap: 12px">
          <img v-if="data.item.image" :src="data.item.image" class="idv-img" alt="" />
          <span v-else class="idv-img" style="display: grid; place-items: center; font-weight: 800; font-size: 30px; color: var(--muted); background: var(--brand-soft)">{{ initials() }}</span>
          <div class="grow" style="min-width: 0">
            <div style="font-weight: 800; font-size: 16px; line-height: 1.25">{{ data.item.item_name }}</div>
            <div class="tiny muted">{{ data.item.item_code }}</div>
            <div v-if="data.item.item_group" class="tiny muted">{{ t('item.group') }}: {{ data.item.item_group }}</div>
          </div>
        </div>
        <div class="row between mt12" style="align-items: flex-end">
          <div>
            <div class="tiny muted">{{ t('item.totalStock') }}</div>
            <div style="font-size: 28px; font-weight: 800; color: var(--brand)">{{ fmt(data.total) }} <span class="small muted">{{ data.uom }}</span></div>
          </div>
          <div v-if="data.barcodes.length" class="tiny muted" style="text-align: right">
            {{ t('item.barcode') }}<br /><b>{{ data.barcodes.join(', ') }}</b>
          </div>
        </div>
        <div v-if="data.restricted" class="tiny muted mt8"><Icon name="lock" /> {{ t('balance.restricted') }}: {{ data.warehouses.join(', ') }}</div>
      </div>

      <!-- Aksi cepat (ikut Stock Ops Settings) -->
      <div v-if="master.menuOn('se_in') || master.menuOn('se_out') || master.menuOn('transfer')" style="display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; gap: 8px; margin-top: 12px">
        <button v-if="master.menuOn('se_in')" class="btn" style="background: #16a34a; color: #fff; flex-direction: column; gap: 2px; padding: 12px 6px; font-size: 12px" @click="quick('SE_IN')"><Icon name="stock-in" /><span>{{ t('item.stockIn') }}</span></button>
        <button v-if="master.menuOn('se_out')" class="btn" style="background: #dc2626; color: #fff; flex-direction: column; gap: 2px; padding: 12px 6px; font-size: 12px" @click="quick('SE_OUT')"><Icon name="stock-out" /><span>{{ t('item.stockOut') }}</span></button>
        <button v-if="master.menuOn('transfer')" class="btn" style="background: #ea580c; color: #fff; flex-direction: column; gap: 2px; padding: 12px 6px; font-size: 12px" @click="quick('SE_TRANSFER')"><Icon name="transfer" /><span>{{ t('item.transfer') }}</span></button>
      </div>

      <!-- Stok per gudang -->
      <div class="section-title">{{ t('item.perWarehouse') }}</div>
      <div v-if="!data.stock.length" class="empty" style="padding: 24px"><div class="big"><Icon name="box" /></div>{{ t('item.noStock') }}</div>
      <div v-else class="card" style="padding: 4px 14px">
        <div v-for="b in data.stock" :key="b.warehouse" class="item-line">
          <div class="grow truncate"><Icon name="warehouse" /> {{ b.warehouse }}</div>
          <div style="text-align: right">
            <div style="font-weight: 800">{{ fmt(b.actual_qty) }} <span class="tiny muted">{{ data.uom }}</span></div>
            <div v-if="b.reserved_qty" class="tiny muted">{{ t('balance.reserved') }} {{ fmt(b.reserved_qty) }}</div>
          </div>
        </div>
      </div>

      <!-- Mutasi terakhir -->
      <div class="section-title">{{ t('item.movements') }}</div>
      <div v-if="!data.movements.length" class="empty" style="padding: 24px"><div class="big"><Icon name="movement" /></div>{{ t('movement.empty') }}</div>
      <div v-else class="card" style="padding: 4px 14px">
        <div v-for="(m, i) in data.movements" :key="i" class="move-row">
          <div class="grow" style="min-width: 0">
            <div class="tiny muted truncate"><span class="move-badge">{{ m.voucher_type }}</span> {{ m.voucher_no }}</div>
            <div class="tiny muted truncate"><Icon name="warehouse" /> {{ m.warehouse }} · {{ dt(m) }}</div>
          </div>
          <div style="text-align: right">
            <div class="move-qty" :class="m.actual_qty >= 0 ? 'in' : 'out'">{{ m.actual_qty >= 0 ? '+' : '' }}{{ fmt(m.actual_qty) }}</div>
            <div class="tiny muted">{{ t('movement.sisa') }} {{ fmt(m.qty_after_transaction) }}</div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
