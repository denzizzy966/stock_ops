<script setup>
import { reactive, computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useDocs } from '../stores/docs'
import { useI18n, LANGS } from '../lib/i18n'
import { useMaster } from '../stores/master'
import { pushSupported, isSubscribed, enablePush, disablePush, sendTest } from '../lib/push'
import AppBar from '../components/AppBar.vue'
import SearchSelect from '../components/SearchSelect.vue'

const app = useApp()
const docs = useDocs()
const master = useMaster()
const router = useRouter()
const { t } = useI18n()

const form = reactive({ ...app.settings })
const pending = computed(() => docs.pendingCount)
const COMPANIES = computed(() => master.companyNames)
// Company dikunci bila berasal dari Employee user (server-driven).
const companyReadOnly = computed(() => !!(master.defaults && master.defaults.company_read_only))
const serverCompany = computed(() => (master.defaults && master.defaults.company) || form.company)
const WAREHOUSES = computed(() => master.warehousesForCompany(companyReadOnly.value ? serverCompany.value : form.company))

// Profil karyawan (dari Employee via bootstrap) — hanya baris terisi yang ditampilkan.
const profileRows = computed(() => {
  const e = master.employee || {}
  const company = (master.defaults && master.defaults.company) || e.company || app.settings.company
  const whs = master.userWarehouses && master.userWarehouses.length
    ? master.userWarehouses.join(', ')
    : t('settings.allWarehouses')
  const rows = [
    { label: 'settings.company', value: company },
    { label: 'settings.warehouse', value: whs },
    { label: 'settings.department', value: e.department },
    { label: 'settings.branch', value: e.branch },
    { label: 'settings.grade', value: e.grade },
    { label: 'settings.designation', value: e.designation }
  ]
  return rows.filter((r) => r.value)
})

const themes = computed(() => [
  { v: 'system', label: t('settings.themeSystem') },
  { v: 'light', label: t('settings.themeLight') },
  { v: 'dark', label: t('settings.themeDark') }
])

// Bahasa & tema diterapkan langsung agar efeknya terlihat seketika.
function setLang(code) {
  form.lang = code
  app.saveSettings({ lang: code, langUserSet: true })
}
function setTheme(v) {
  form.theme = v
  app.saveSettings({ theme: v })
}
function setDesign(v) {
  form.design = v
  app.saveSettings({ design: v })
}
const designs = computed(() => [
  { v: 'blue', label: t('settings.designBlue') },
  { v: 'classic', label: t('settings.designClassic') },
  { v: 'compact', label: t('settings.designCompact') }
])
function save() {
  app.saveSettings({ ...form })
  app.notify(t('toast.settingsSaved'), 'success')
}
// ===== Push notification =====
const notifSupported = pushSupported()
const notifOn = ref(false)
const notifBusy = ref(false)
onMounted(async () => {
  if (notifSupported) notifOn.value = await isSubscribed()
})
async function toggleNotif() {
  if (notifBusy.value) return
  notifBusy.value = true
  try {
    if (notifOn.value) {
      await disablePush()
      notifOn.value = false
      app.notify(t('toast.notifOff'), 'info')
    } else {
      await enablePush()
      notifOn.value = true
      app.notify(t('toast.notifOn'), 'success')
    }
  } catch (e) {
    notifOn.value = await isSubscribed()
    if (e && e.message === 'denied') app.notify(t('toast.notifDenied'), 'warn')
    else app.notify(e && e.message ? e.message : String(e), 'error')
  } finally {
    notifBusy.value = false
  }
}
async function testNotif() {
  try {
    await sendTest()
    app.notify(t('toast.testSent'), 'success')
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  }
}

function downloadApk() {
  if (!master.flutterApkUrl) {
    app.notify(t('settings.apkUnavailable'), 'warn')
    return
  }
  window.open(master.flutterApkUrl, '_blank')
}
async function installPwa() {
  if (!app.installPrompt) {
    app.notify(t('settings.pwaUnavailable'), 'info')
    return
  }
  await app.promptInstall()
}
async function logout() {
  const reloading = await app.logout()
  // Web melakukan reload penuh ke /login; native (SPA) pindah ke layar login.
  if (!reloading) router.replace('/login')
}
function clearData() {
  if (confirm(t('settings.confirmClear'))) {
    docs.docs = []
    docs.persist()
    app.notify(t('toast.dataCleared'), 'success')
  }
}
</script>

<template>
  <AppBar :title="t('settings.title')" :showNet="false" />
  <div class="content">
    <div class="card">
      <div class="row">
        <span class="lead-icon" style="background: var(--brand)"><Icon name="user" /></span>
        <div class="grow" style="min-width: 0">
          <div class="truncate" style="font-weight: 700">{{ master.employee?.employee_name || app.user?.name }}</div>
          <div class="tiny muted truncate">{{ app.user?.email }}</div>
        </div>
      </div>
      <div v-if="profileRows.length" class="profile-grid mt12">
        <template v-for="r in profileRows" :key="r.label">
          <div class="tiny muted">{{ t(r.label) }}</div>
          <div class="small" style="text-align: right; font-weight: 600; min-width: 0; overflow-wrap: anywhere">{{ r.value }}</div>
        </template>
      </div>
    </div>

    <!-- Sync / Outbox dipindah ke sini -->
    <div class="section-title">{{ t('settings.syncOutbox') }}</div>
    <button class="list-item" style="width: 100%; text-align: left; border: 0; cursor: pointer" @click="router.push('/sync')">
      <span class="lead-icon" style="background: var(--brand)"><Icon name="refresh" /></span>
      <div class="grow">
        <div style="font-weight: 700">{{ t('settings.syncOutbox') }}</div>
        <div class="tiny muted">{{ t('settings.syncOutboxDesc') }}</div>
      </div>
      <span v-if="pending" class="badge-status s-pending">{{ pending }}</span>
      <span style="font-size: 22px; color: var(--muted); margin-left: 6px">›</span>
    </button>

    <button class="list-item" style="width: 100%; text-align: left; border: 0; cursor: pointer; margin-top: 10px" @click="router.push('/reports')">
      <span class="lead-icon" style="background: var(--brand)"><Icon name="report" /></span>
      <div class="grow">
        <div style="font-weight: 700">{{ t('settings.reports') }}</div>
        <div class="tiny muted">{{ t('settings.reportsDesc') }}</div>
      </div>
      <span style="font-size: 22px; color: var(--muted); margin-left: 6px">›</span>
    </button>

    <div class="section-title">{{ t('settings.appearance') }}</div>
    <div class="card">
      <div class="field">
        <label>{{ t('settings.language') }}</label>
        <div class="seg">
          <button v-for="l in LANGS" :key="l.code" :class="{ active: form.lang === l.code }" @click="setLang(l.code)">
            {{ l.label }}
          </button>
        </div>
      </div>
      <div class="field">
        <label>{{ t('settings.theme') }}</label>
        <div class="seg">
          <button v-for="th in themes" :key="th.v" :class="{ active: form.theme === th.v }" @click="setTheme(th.v)">
            {{ th.label }}
          </button>
        </div>
      </div>
      <div class="field" style="margin: 0">
        <label>{{ t('settings.design') }}</label>
        <div style="display: grid; gap: 8px">
          <button
            v-for="d in designs"
            :key="d.v"
            class="btn"
            :class="form.design === d.v ? 'brand' : ''"
            style="justify-content: space-between"
            @click="setDesign(d.v)"
          >
            <span>{{ d.label }}</span>
            <span v-if="form.design === d.v"><Icon name="check" /></span>
          </button>
        </div>
      </div>
    </div>

    <template v-if="master.isManager">
      <div class="section-title">{{ t('settings.defaults') }}</div>
      <div class="card">
        <div class="field">
          <label>{{ t('settings.companyDefault') }}</label>
          <template v-if="companyReadOnly">
            <input type="text" :value="serverCompany" readonly disabled />
            <div class="tiny muted" style="margin-top: 4px">{{ t('form.companyFromAccount') }}</div>
          </template>
          <SearchSelect v-else v-model="form.company" :options="COMPANIES" :placeholder="t('settings.companyDefault')" />
        </div>
        <div class="field">
          <label>{{ t('settings.srcDefault') }}</label>
          <SearchSelect v-model="form.defaultSourceWarehouse" :options="WAREHOUSES" :search-placeholder="t('form.whSearch')" :empty-text="t('form.whEmpty')" :placeholder="t('settings.srcDefault')" />
        </div>
        <div class="field" style="margin: 0">
          <label>{{ t('settings.tgtDefault') }}</label>
          <SearchSelect v-model="form.defaultTargetWarehouse" :options="WAREHOUSES" :search-placeholder="t('form.whSearch')" :empty-text="t('form.whEmpty')" :placeholder="t('settings.tgtDefault')" />
        </div>
      </div>
    </template>

    <template v-if="notifSupported && master.menuOn('notifications')">
      <div class="section-title">{{ t('settings.notif') }}</div>
      <div class="card">
        <div class="row between">
          <div><div style="font-weight: 600">{{ t('settings.enableNotif') }}</div><div class="tiny muted">{{ t('settings.enableNotifDesc') }}</div></div>
          <label class="switch">
            <input type="checkbox" :checked="notifOn" :disabled="notifBusy" @change="toggleNotif" />
            <span class="slider"></span>
          </label>
        </div>
        <button v-if="notifOn" class="btn sm mt12" @click="testNotif"><Icon name="bell" /> {{ t('settings.testNotif') }}</button>
      </div>
    </template>

    <template v-if="master.isManager">
      <div class="section-title">{{ t('settings.photoSync') }}</div>
      <div class="card">
        <label class="row between" style="cursor: pointer">
          <div><div style="font-weight: 600">{{ t('settings.privatePhoto') }}</div><div class="tiny muted">{{ t('settings.privatePhotoDesc') }}</div></div>
          <input type="checkbox" v-model="form.privatePhotos" style="width: 22px; height: 22px" />
        </label>
        <hr style="border: 0; border-top: 1px solid var(--line); margin: 12px 0" />
        <label class="row between" style="cursor: pointer">
          <div><div style="font-weight: 600">{{ t('settings.autoSync') }}</div><div class="tiny muted">{{ t('settings.autoSyncDesc') }}</div></div>
          <input type="checkbox" v-model="form.autoSync" style="width: 22px; height: 22px" />
        </label>
      </div>

      <button class="btn brand block mt16" @click="save">{{ t('settings.saveSettings') }}</button>
    </template>

    <div class="section-title">{{ t('settings.getApp') }}</div>
    <div class="card">
      <button v-if="master.flutterApkUrl" class="list-item" style="width: 100%; text-align: left; border: 0; cursor: pointer" @click="downloadApk">
        <span class="lead-icon" style="background: #16a34a"><Icon name="download" /></span>
        <div class="grow">
          <div style="font-weight: 700">{{ t('settings.downloadApk') }}</div>
          <div class="tiny muted">{{ t('settings.downloadApkDesc') }}</div>
        </div>
        <span style="font-size: 22px; color: var(--muted)">›</span>
      </button>
      <hr v-if="master.flutterApkUrl" style="border: 0; border-top: 1px solid var(--line); margin: 10px 0" />
      <button class="list-item" style="width: 100%; text-align: left; border: 0; cursor: pointer" @click="installPwa">
        <span class="lead-icon" style="background: var(--brand)"><Icon name="install" /></span>
        <div class="grow">
          <div style="font-weight: 700">{{ t('settings.installPwa') }}</div>
          <div class="tiny muted">{{ t('settings.installPwaDesc') }}</div>
        </div>
        <span style="font-size: 22px; color: var(--muted)">›</span>
      </button>
    </div>

    <template v-if="master.isManager">
      <div class="section-title">{{ t('settings.other') }}</div>
      <div class="card">
        <div class="row between small"><span class="muted">{{ t('settings.backend') }}</span><span>erp.localhost</span></div>
        <div class="row between small mt8"><span class="muted">{{ t('settings.mockVersion') }}</span><span>P0 · 0.0.1</span></div>
      </div>

      <button class="btn block mt12" @click="clearData">{{ t('settings.clearData') }}</button>
    </template>
    <button class="btn danger block mt12" @click="logout">{{ t('common.logout') }}</button>
    <div style="height: 8px"></div>
  </div>
</template>

<style scoped>
.profile-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 6px 12px;
  align-items: baseline;
  border-top: 1px solid var(--line);
  padding-top: 10px;
}
</style>
