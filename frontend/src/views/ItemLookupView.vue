<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useMaster } from '../stores/master'
import { useApp } from '../stores/app'
import { useI18n } from '../lib/i18n'
import { resolveItem } from '../lib/service'
import AppBar from '../components/AppBar.vue'
import SearchInput from '../components/SearchInput.vue'
import BarcodeScanner from '../components/BarcodeScanner.vue'

const router = useRouter()
const master = useMaster()
const app = useApp()
const { t } = useI18n()

const q = ref('')
const showScanner = ref(false)

const results = computed(() => {
  const s = q.value.trim().toLowerCase()
  if (!s) return []
  return master.itemList
    .filter(
      (i) =>
        (i.item_name || '').toLowerCase().includes(s) ||
        (i.item_code || '').toLowerCase().includes(s) ||
        (i.barcode || '').includes(s)
    )
    .slice(0, 50)
})

function initials(it) {
  return (it.item_name || it.item_code || '?').trim().charAt(0).toUpperCase()
}
function open(code) {
  router.push(`/item/${encodeURIComponent(code)}`)
}

async function onDetected(code) {
  showScanner.value = false
  const local = master.itemList.find((i) => i.barcode === code || i.item_code === code)
  if (local) return open(local.item_code)
  try {
    const rc = await resolveItem(code)
    if (rc) return open(rc)
    app.notify(t('lookup.notFound'), 'warn')
    q.value = code
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  }
}
</script>

<template>
  <AppBar :title="t('lookup.title')" back />
  <div class="content">
    <div class="toolbar">
      <div class="row" style="gap: 8px">
        <SearchInput v-model="q" :placeholder="t('lookup.search')" class="grow" />
        <button class="btn brand" style="padding: 12px 14px" @click="showScanner = true" :title="t('scan.title')"><Icon name="camera" /></button>
      </div>
    </div>

    <div v-if="!results.length" class="empty">
      <div class="big"><Icon name="search" /></div>
      {{ t('lookup.empty') }}
      <div class="tiny muted mt8">{{ t('lookup.scanHint') }} <Icon name="camera" /></div>
    </div>

    <div
      v-for="it in results"
      :key="it.item_code"
      class="list-item"
      style="cursor: pointer; margin-bottom: 10px"
      @click="open(it.item_code)"
    >
      <img v-if="it.image" :src="it.image" class="thumb" alt="" />
      <span v-else class="thumb" style="display: grid; place-items: center; font-weight: 700; color: var(--muted)">{{ initials(it) }}</span>
      <div class="grow">
        <div class="truncate" style="font-weight: 600">{{ it.item_name }}</div>
        <div class="tiny muted truncate">{{ it.item_code }} · {{ it.stock_uom }}<span v-if="it.barcode"> · {{ it.barcode }}</span></div>
      </div>
      <span style="font-size: 22px; color: var(--muted)">›</span>
    </div>

    <BarcodeScanner v-if="showScanner" @detected="onDetected" @close="showScanner = false" />
  </div>
</template>
