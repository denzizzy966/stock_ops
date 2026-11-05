<script setup>
import { computed, ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useDocs } from '../stores/docs'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { DOC_TYPE_LIST, DOC_TYPES } from '../data/mock'
import { HR_KINDS } from '../lib/hr'
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

// Menu peluncur (semua tile identik → pasti seragam). `key` = flag Stock Ops Settings,
// `id` = kunci tetap untuk pin/sembunyikan per user (jangan diganti: tersimpan di akun user).
const menuAll = [
  { id: 'lookup', icon: 'search', color: '#0ea5e9', label: 'home.menu.lookup', to: '/lookup', key: 'scan' },
  { id: 'balance', icon: 'warehouse', color: 'var(--brand)', label: 'home.menu.balance', to: '/balance', key: 'stock_balance' },
  { id: 'movement', icon: 'movement', color: '#2563eb', label: 'home.menu.movement', to: '/movement', key: 'movement' },
  { id: 'low', icon: 'warning', color: 'var(--warn)', label: 'home.menu.low', to: '/low', key: 'low_stock' },
  { id: 'transfer', icon: 'transfer', color: '#ea580c', label: 'home.menu.transfer', to: '/quick-transfer', key: 'transfer' },
  { id: 'opname', icon: 'list', color: '#7c3aed', label: 'home.menu.opname', to: '/opname', key: 'opname' }
]

// Semua tile yang DIIZINKAN admin untuk user ini (Stock Ops Settings + role). Preferensi user
// hanya bisa memindahkan ke Favorit atau menyembunyikan — tidak bisa memunculkan menu yang dimatikan.
const tiles = computed(() => {
  const out = menuAll
    .filter((m) => master.menuOn(m.key))
    .map((m) => ({ ...m, group: 'menu', label: t(m.label) }))
  if (master.isApprover)
    out.push({ id: 'approvals', group: 'menu', icon: 'check-circle', color: '#b45309', label: t('approval.menu'), to: '/approvals', badge: master.pendingApprovals })
  if (master.rtpOn)
    out.push({ id: 'rtp', group: 'menu', icon: 'receipt', color: '#0f766e', label: t('rtp.menu'), to: '/rtp', badge: master.rtp.todo })
  for (const [kind, k] of Object.entries(HR_KINDS))
    if (master.hrOn(kind))
      out.push({ id: 'hr:' + kind, group: 'menu', icon: k.icon, color: k.color, label: t('hr.menu.' + kind), to: '/hr/' + kind, badge: (master.hr[kind] || {}).todo })
  for (const ty of DOC_TYPE_LIST.filter((x) => master.menuOn(x.key.toLowerCase())))
    out.push({ id: 'create:' + ty.key, group: 'create', icon: ty.icon, color: ty.color, label: t('docType.' + ty.key), to: `/form/${ty.key}` })
  return out
})
const byId = computed(() => Object.fromEntries(tiles.value.map((x) => [x.id, x])))

// ── Atur Beranda ──
const editing = ref(false)
const saving = ref(false)
const draft = reactive({ pinned: [], hidden: [] })
const prefs = computed(() => (editing.value ? draft : master.homePrefs))
const isPinned = (id) => prefs.value.pinned.includes(id)
const isHidden = (id) => prefs.value.hidden.includes(id)
const favorites = computed(() => prefs.value.pinned.map((id) => byId.value[id]).filter(Boolean))
// Mode biasa: tile Favorit tidak diulang di bagian asalnya; tile tersembunyi tidak tampil.
// Mode atur: semua tile tampil di bagian asalnya supaya bisa di-pin / dimunculkan lagi.
const shown = (group) => tiles.value.filter((x) => x.group === group && (editing.value || (!isPinned(x.id) && !isHidden(x.id))))
const menuTiles = computed(() => shown('menu'))
const createTiles = computed(() => shown('create'))
const showRecent = computed(() => master.menuOn('documents') && (editing.value || !isHidden('section:recent')))
const hiddenCount = computed(() => master.homePrefs.hidden.filter((id) => byId.value[id] || id === 'section:recent').length)

function startEdit() {
  draft.pinned = [...master.homePrefs.pinned]
  draft.hidden = [...master.homePrefs.hidden]
  editing.value = true
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
function togglePin(id) {
  if (isPinned(id)) draft.pinned = draft.pinned.filter((x) => x !== id)
  else {
    draft.pinned = [...draft.pinned, id]
    draft.hidden = draft.hidden.filter((x) => x !== id) // yang di-pin pasti tampil
  }
}
function toggleHide(id) {
  if (isHidden(id)) draft.hidden = draft.hidden.filter((x) => x !== id)
  else {
    draft.hidden = [...draft.hidden, id]
    draft.pinned = draft.pinned.filter((x) => x !== id)
  }
}
// Geser Favorit ke kiri (urutan Favorit = urutan di Beranda).
function moveLeft(id) {
  const i = draft.pinned.indexOf(id)
  if (i > 0) {
    const p = [...draft.pinned]
    ;[p[i - 1], p[i]] = [p[i], p[i - 1]]
    draft.pinned = p
  }
}
function resetPrefs() {
  draft.pinned = []
  draft.hidden = []
}
async function saveEdit() {
  saving.value = true
  const ok = await master.setHomePrefs({ pinned: draft.pinned, hidden: draft.hidden })
  saving.value = false
  editing.value = false
  app.notify(ok ? t('home.prefsSaved') : t('home.prefsSavedOffline'), ok ? 'success' : 'info')
}
function openTile(x) {
  if (!editing.value) router.push(x.to)
}

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
  <div class="content" :class="{ 'home-editing': editing }">
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

    <!-- Bar mode atur -->
    <div v-if="editing" class="edit-bar mt12">
      <div class="small" style="font-weight: 700">{{ t('home.editTitle') }}</div>
      <div class="tiny muted" style="margin-top: 2px">{{ t('home.editHint') }}</div>
      <div class="row" style="gap: 8px; margin-top: 10px">
        <button class="btn sm" :disabled="saving" @click="resetPrefs">{{ t('home.editReset') }}</button>
        <span class="grow"></span>
        <button class="btn sm" :disabled="saving" @click="editing = false">{{ t('common.cancel') }}</button>
        <button class="btn sm brand" :disabled="saving" @click="saveEdit">{{ t('common.save') }}</button>
      </div>
    </div>

    <!-- Alert stok menipis -->
    <button v-if="lowCount && !editing" class="alert-low mt12" @click="router.push('/low')">
      <span class="al-ic"><Icon name="warning" /></span>
      <span class="grow" style="text-align: left; min-width: 0">
        <span style="display: block; font-weight: 700">{{ t('home.lowAlert', { n: lowCount }) }}</span>
        <span class="tiny" style="opacity: 0.85">{{ t('home.lowAlertSub') }}</span>
      </span>
      <span class="al-go">{{ t('home.viewAlerts') }} ›</span>
    </button>

    <!-- Favorit (menu yang di-pin user) -->
    <template v-if="favorites.length">
      <div class="row between sec-row">
        <div class="section-title" style="margin: 0"><Icon name="pin" /> {{ t('home.favorites') }}</div>
        <button v-if="!editing" class="link-btn" @click="startEdit"><Icon name="sliders" /> {{ t('home.edit') }}</button>
      </div>
      <div class="launch-grid">
        <div v-for="x in favorites" :key="'fav-' + x.id" class="tile-wrap" :data-id="'fav:' + x.id">
          <button class="launch-tile" style="position: relative" @click="openTile(x)">
            <span class="li" :style="{ background: x.color }"><Icon :name="x.icon" /></span>
            <span class="lt">{{ x.label }}</span>
            <span v-if="x.badge && !editing" class="tile-badge">{{ x.badge }}</span>
          </button>
          <template v-if="editing">
            <button class="tile-act pin on" :aria-label="t('home.unpin')" @click="togglePin(x.id)"><Icon name="pin" /></button>
            <button v-if="favorites[0].id !== x.id" class="tile-act move" :aria-label="t('home.moveLeft')" @click="moveLeft(x.id)">‹</button>
          </template>
        </div>
      </div>
    </template>

    <!-- Menu peluncur seragam -->
    <template v-if="menuTiles.length || (!favorites.length && !editing)">
      <div class="row between sec-row">
        <div class="section-title" style="margin: 0">{{ t('home.menuTitle') }}</div>
        <button v-if="!editing && !favorites.length" class="link-btn" @click="startEdit"><Icon name="sliders" /> {{ t('home.edit') }}</button>
      </div>
      <div v-if="menuTiles.length" class="launch-grid">
        <div v-for="x in menuTiles" :key="x.id" class="tile-wrap" :data-id="x.id" :class="{ hidden: editing && isHidden(x.id) }">
          <button class="launch-tile" style="position: relative" @click="openTile(x)">
            <span class="li" :style="{ background: x.color }"><Icon :name="x.icon" /></span>
            <span class="lt">{{ x.label }}</span>
            <span v-if="x.badge && !editing" class="tile-badge">{{ x.badge }}</span>
          </button>
          <template v-if="editing">
            <button class="tile-act pin" :class="{ on: isPinned(x.id) }" :aria-label="t('home.pin')" @click="togglePin(x.id)"><Icon name="pin" /></button>
            <button class="tile-act eye" :aria-label="t('home.hide')" @click="toggleHide(x.id)"><Icon :name="isHidden(x.id) ? 'eyeoff' : 'eye'" /></button>
          </template>
        </div>
      </div>
      <div v-else class="tiny muted" style="margin: 0 4px">{{ t('home.allHidden') }}</div>
    </template>

    <!-- Buat dokumen -->
    <template v-if="createTiles.length">
      <div class="section-title">{{ t('home.quickCreate') }}</div>
      <div class="quick-grid">
        <div v-for="x in createTiles" :key="x.id" class="tile-wrap" :data-id="x.id" :class="{ hidden: editing && isHidden(x.id) }">
          <button class="quick-tile" :style="{ background: x.color }" @click="openTile(x)">
            <Icon :name="x.icon" class="qt-ic" />
            <span class="qt-lbl">{{ x.label }}</span>
          </button>
          <template v-if="editing">
            <button class="tile-act pin" :class="{ on: isPinned(x.id) }" :aria-label="t('home.pin')" @click="togglePin(x.id)"><Icon name="pin" /></button>
            <button class="tile-act eye" :aria-label="t('home.hide')" @click="toggleHide(x.id)"><Icon :name="isHidden(x.id) ? 'eyeoff' : 'eye'" /></button>
          </template>
        </div>
      </div>
    </template>

    <!-- Terbaru -->
    <template v-if="showRecent">
      <div class="row between" style="margin-top: 18px">
        <div class="section-title" style="margin: 0 4px">{{ t('home.recent') }}</div>
        <button v-if="editing" class="btn sm" @click="toggleHide('section:recent')">
          <Icon :name="isHidden('section:recent') ? 'eyeoff' : 'eye'" />
          {{ isHidden('section:recent') ? t('home.hidden') : t('home.shown') }}
        </button>
        <router-link v-else to="/docs" class="small" style="color: var(--brand); font-weight: 600">{{ t('common.viewAll') }}</router-link>
      </div>

      <div :class="{ 'sec-hidden': editing && isHidden('section:recent') }">
        <div v-if="!recent.length" class="empty">
          <div class="big"><Icon name="box" /></div>
          {{ t('home.emptyDocs') }}
        </div>

        <div
          v-for="d in recent"
          :key="d.localId"
          class="list-item"
          @click="!editing && router.push(`/doc/${d.localId}`)"
          style="cursor: pointer"
        >
          <span class="lead-icon" :style="{ background: DOC_TYPES[d.type].color }"><Icon :name="DOC_TYPES[d.type].icon" /></span>
          <div class="grow">
            <div class="truncate" style="font-weight: 600">{{ d.remoteName || t('home.draftLocal') }}</div>
            <div class="tiny muted">{{ t('docType.' + d.type) }} · {{ d.items.length }} {{ t('common.items') }} · {{ fmtDateTime(d.createdAt) }}</div>
          </div>
          <StatusBadge :status="d.status" :submitted="d.submitted" />
        </div>
      </div>
    </template>

    <div v-if="!editing && hiddenCount" class="tiny muted" style="text-align: center; margin: 18px 0 6px">
      {{ t('home.hiddenNote', { n: hiddenCount }) }} · <button class="link-btn" style="display: inline" @click="startEdit">{{ t('home.edit') }}</button>
    </div>
  </div>
</template>

<style scoped>
.sec-row { margin: 18px 4px 8px; gap: 8px; }
.link-btn { background: none; border: 0; padding: 0; color: var(--brand); font-weight: 700; font-size: 12px; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; }
.tile-wrap { position: relative; }
.tile-wrap > .launch-tile, .tile-wrap > .quick-tile { width: 100%; height: 100%; }
.tile-wrap.hidden > .launch-tile, .tile-wrap.hidden > .quick-tile { opacity: 0.35; filter: grayscale(0.6); }
.home-editing .tile-wrap > .launch-tile, .home-editing .tile-wrap > .quick-tile { outline: 2px dashed var(--line, #d1d5db); outline-offset: -2px; }
.tile-badge {
  position: absolute; top: 6px; right: 10px; min-width: 18px; height: 18px; padding: 0 5px; border-radius: 9px;
  background: var(--danger, #dc2626); color: #fff; font-size: 11px; font-weight: 700; display: grid; place-items: center;
}
.tile-act {
  position: absolute; top: -6px; width: 30px; height: 30px; border-radius: 50%; border: 0; display: grid; place-items: center;
  font-size: 13px; cursor: pointer; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25); background: var(--card, #fff); color: var(--muted, #6b7280);
}
.tile-act.pin { left: -6px; }
.tile-act.pin.on { background: var(--brand); color: #fff; }
.tile-act.eye { right: -6px; }
.tile-act.move { right: -6px; font-size: 20px; font-weight: 700; line-height: 1; }
.edit-bar { background: var(--card); border: 2px solid var(--brand); border-radius: var(--radius, 14px); padding: 12px 14px; }
.sec-hidden { opacity: 0.35; }
</style>
