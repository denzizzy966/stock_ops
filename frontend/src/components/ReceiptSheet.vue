<script setup>
import { ref, onMounted } from 'vue'
import { useApp } from '../stores/app'
import { useI18n } from '../lib/i18n'
import { listReturnableReceipts } from '../lib/service'
import Sheet from './Sheet.vue'
import SearchInput from './SearchInput.vue'

const props = defineProps({ company: { type: String, default: '' }, supplier: { type: String, default: '' } })
const emit = defineEmits(['pick', 'close'])
const app = useApp()
const { t } = useI18n()
const q = ref('')
const loading = ref(false)
const receipts = ref([])

async function load() {
  loading.value = true
  try {
    receipts.value =
      (await listReturnableReceipts(props.company || undefined, props.supplier || undefined, q.value.trim() || undefined)) || []
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
    receipts.value = []
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<template>
  <Sheet :title="t('ret.pickTitle')" @close="emit('close')">
    <div class="row" style="gap: 8px; margin-bottom: 12px">
      <SearchInput v-model="q" :placeholder="t('ret.searchPlaceholder')" class="grow" @keyup.enter="load" />
      <button class="btn brand" style="padding: 12px 14px" @click="load"><Icon name="search" /></button>
    </div>

    <div v-if="loading" class="empty"><div class="big"><Icon name="loading" spin /></div>{{ t('common.loading') }}</div>
    <div v-else-if="!receipts.length" class="empty"><div class="big"><Icon name="inbox" /></div>{{ t('ret.none') }}</div>

    <div v-for="r in receipts" :key="r.name" class="list-item" style="cursor: pointer" @click="emit('pick', r)">
      <span class="lead-icon" style="background: #b45309"><Icon name="box" /></span>
      <div class="grow" style="min-width: 0">
        <div class="truncate" style="font-weight: 600">{{ r.name }}</div>
        <div class="tiny muted truncate">
          {{ r.supplier_name || r.supplier }} · {{ r.posting_date }}
          <span v-if="Number(r.per_returned) > 0"> · {{ t('ret.partlyReturned', { pct: Math.round(Number(r.per_returned)) }) }}</span>
        </div>
      </div>
      <span style="font-size: 22px; color: var(--brand)">›</span>
    </div>
  </Sheet>
</template>
