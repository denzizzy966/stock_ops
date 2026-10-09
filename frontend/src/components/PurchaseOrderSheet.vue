<script setup>
import { ref, onMounted } from 'vue'
import { useApp } from '../stores/app'
import { useI18n } from '../lib/i18n'
import { listOpenPurchaseOrders } from '../lib/service'
import Sheet from './Sheet.vue'
import SearchInput from './SearchInput.vue'

const props = defineProps({ company: { type: String, default: '' }, supplier: { type: String, default: '' } })
const emit = defineEmits(['pick', 'close'])
const app = useApp()
const { t } = useI18n()
const q = ref('')
const loading = ref(false)
const pos = ref([])

async function load() {
  loading.value = true
  try {
    pos.value = (await listOpenPurchaseOrders(props.company, props.supplier, q.value.trim() || undefined)) || []
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
    pos.value = []
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<template>
  <Sheet :title="t('po.title')" @close="emit('close')">
    <div class="row" style="gap: 8px; margin-bottom: 12px">
      <SearchInput v-model="q" :placeholder="t('po.searchPlaceholder')" class="grow" @keyup.enter="load" />
      <button class="btn brand" style="padding: 12px 14px" @click="load"><Icon name="search" /></button>
    </div>

    <div v-if="loading" class="empty"><div class="big"><Icon name="loading" spin /></div>{{ t('common.loading') }}</div>
    <div v-else-if="!pos.length" class="empty"><div class="big"><Icon name="inbox" /></div>{{ t('po.none') }}</div>

    <div v-for="po in pos" :key="po.name" class="list-item" style="cursor: pointer" @click="emit('pick', po)">
      <span class="lead-icon" style="background: #0891b2"><Icon name="receipt" /></span>
      <div class="grow" style="min-width: 0">
        <div class="truncate" style="font-weight: 600">{{ po.name }}</div>
        <div class="tiny muted truncate">{{ po.supplier_name || po.supplier }} · {{ po.transaction_date }} · {{ po.status }}</div>
      </div>
      <span style="font-size: 22px; color: var(--brand)">›</span>
    </div>
  </Sheet>
</template>
