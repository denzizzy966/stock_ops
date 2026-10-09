<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useDocs } from '../stores/docs'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { DOC_TYPE_LIST, DOC_TYPES } from '../data/mock'
import { getLowStock } from '../lib/service'
import AppBar from '../components/AppBar.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { fmtDateTime } from '../lib/util'

const app = useApp()
const docs = useDocs()
const master = useMaster()
const router = useRouter()
const { t, locale } = useI18n()

const recent = computed(() => docs.sorted.slice(0, 4))

// Menu peluncur (semua tile identik → pasti seragam). `key` = flag Stock Ops Settings.
const menuAll = [
  { icon: 'search', color: '#0ea5e9', label: 'home.menu.lookup', to: '/lookup', key: 'scan' },
  { icon: 'warehouse', color: 'var(--brand)', label: 'home.menu.balance', to: '/balance', key: 'stock_balance' },
  { icon: 'movement', color: '#2563eb', label: 'home.menu.movement', to: '/movement', key: 'movement' },
  { icon: 'warning', color: 'var(--warn)', label: 'home.menu.low', to: '/low', key: 'low_stock' },
  { icon: 'transfer', color: '#ea580c', label: 'home.menu.transfer', to: '/quick-transfer', key: 'transfer' },
  { icon: 'list', color: '#7c3aed', label: 'home.menu.opname', to: '/opname', key: 'opname' }
]
const menu = computed(() => menuAll.filter((m) => master.menuOn(m.key)))
const createTypes = computed(() => DOC_TYPE_LIST.filter((ty) => master.menuOn(ty.key.toLowerCase())))

// Alert stok menipis
const lowCount = ref(0)
async function loadLow() {
  if (!app.online || !master.menuOn('low_stock')) return
  try {
    const r = await getLowStock(app.settings.company)
    lowCount.value = (r.items || []).length
  } catch {
    lowCount.value = 0
  }
}

// Jam berjalan
const now = ref(new Date())
let timer = null
onMounted(() => {
  loadLow()
  timer = setInterval(() => (now.value = new Date()), 1000)
})
onUnmounted(() => clearInterval(timer))

const clock = computed(() => {
  const p = (n) => String(n).padStart(2, '0')
  const d = now.value
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
})
const dateStr = computed(() =>
  now.value.toLocaleDateString(locale.value === 'id' ? 'id-ID' : 'en-GB', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
  })
)
</script>

<template>
  <AppBar logo bell :bell-count="app.notifUnread" />
  <div class="content">
    <!-- Hero -->
    <div class="hero" style="position: relative; overflow: hidden">
      <div class="row between">
        <div>
          <div class="small" style="opacity: 0.9">{{ t('home.hello', { name: app.user?.name }) }}</div>
          <div style="font-weight: 700; margin-top: 2px; opacity: 0.95">{{ app.settings.company }}</div>
        </div>
      </div>
      <div class="hero-clock">{{ clock }}</div>
      <div class="small" style="opacity: 0.9; text-transform: capitalize">{{ dateStr }}</div>
    </div>

    <div v-if="!app.online" class="banner-offline mt12">{{ t('home.offlineBanner') }}</div>

    <!-- Alert stok menipis -->
    <button v-if="lowCount" class="alert-low mt12" @click="router.push('/low')">
      <span class="al-ic"><Icon name="warning" /></span>
      <span class="grow" style="text-align: left; min-width: 0">
        <span style="display: block; font-weight: 700">{{ t('home.lowAlert', { n: lowCount }) }}</span>
        <span class="tiny" style="opacity: 0.85">{{ t('home.lowAlertSub') }}</span>
      </span>
      <span class="al-go">{{ t('home.viewAlerts') }} ›</span>
    </button>

    <!-- Menu peluncur seragam -->
    <template v-if="menu.length || master.isApprover">
      <div class="section-title">{{ t('home.menuTitle') }}</div>
      <div class="launch-grid">
        <button v-for="m in menu" :key="m.to" class="launch-tile" @click="router.push(m.to)">
          <span class="li" :style="{ background: m.color }"><Icon :name="m.icon" /></span>
          <span class="lt">{{ t(m.label) }}</span>
        </button>
        <button v-if="master.isApprover" class="launch-tile" style="position: relative" @click="router.push('/approvals')">
          <span class="li" style="background: #b45309"><Icon name="check-circle" /></span>
          <span class="lt">{{ t('approval.menu') }}</span>
          <span
            v-if="master.pendingApprovals"
            style="position: absolute; top: 6px; right: 10px; min-width: 18px; height: 18px; padding: 0 5px; border-radius: 9px; background: var(--danger, #dc2626); color: #fff; font-size: 11px; font-weight: 700; display: grid; place-items: center"
          >{{ master.pendingApprovals }}</span>
        </button>
      </div>
    </template>

    <!-- Buat dokumen -->
    <template v-if="createTypes.length">
      <div class="section-title">{{ t('home.quickCreate') }}</div>
      <div class="quick-grid">
        <button
          v-for="ty in createTypes"
          :key="ty.key"
          class="quick-tile"
          :style="{ background: ty.color }"
          @click="router.push(`/form/${ty.key}`)"
        >
          <Icon :name="ty.icon" class="qt-ic" />
          <span class="qt-lbl">{{ t('docType.' + ty.key) }}</span>
        </button>
      </div>
    </template>

    <!-- Terbaru -->
    <template v-if="master.menuOn('documents')">
      <div class="row between" style="margin-top: 18px">
        <div class="section-title" style="margin: 0 4px">{{ t('home.recent') }}</div>
        <router-link to="/docs" class="small" style="color: var(--brand); font-weight: 600">{{ t('common.viewAll') }}</router-link>
      </div>

      <div v-if="!recent.length" class="empty">
        <div class="big"><Icon name="box" /></div>
        {{ t('home.emptyDocs') }}
      </div>

      <div
        v-for="d in recent"
        :key="d.localId"
        class="list-item"
        @click="router.push(`/doc/${d.localId}`)"
        style="cursor: pointer"
      >
        <span class="lead-icon" :style="{ background: DOC_TYPES[d.type].color }"><Icon :name="DOC_TYPES[d.type].icon" /></span>
        <div class="grow">
          <div class="truncate" style="font-weight: 600">{{ d.remoteName || t('home.draftLocal') }}</div>
          <div class="tiny muted">{{ t('docType.' + d.type) }} · {{ d.items.length }} {{ t('common.items') }} · {{ fmtDateTime(d.createdAt) }}</div>
        </div>
        <StatusBadge :status="d.status" :submitted="d.submitted" />
      </div>
    </template>
  </div>
</template>
