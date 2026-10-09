import { defineStore } from 'pinia'
import { COMPANIES, WAREHOUSES } from '../data/mock'
import { useMaster } from './master'
import { isNative } from '../lib/platform'

const LS = 'stockops.app'

function load() {
  try {
    return JSON.parse(localStorage.getItem(LS)) || {}
  } catch {
    return {}
  }
}

export const useApp = defineStore('app', {
  state: () => {
    const saved = load()
    return {
      // sesi (mock)
      user: saved.user || null, // { name, email }
      // status jaringan: gabungan navigator.onLine + override manual (untuk uji offline)
      browserOnline: navigator.onLine,
      forceOffline: saved.forceOffline || false,
      // pengaturan default
      settings: {
        company: COMPANIES[0],
        defaultSourceWarehouse: WAREHOUSES[0],
        defaultTargetWarehouse: WAREHOUSES[3],
        privatePhotos: true,
        autoSync: true,
        lang: 'id', // 'id' | 'en'
        langUserSet: false, // true bila user pilih bahasa manual (abaikan default server)
        theme: 'system', // 'system' | 'light' | 'dark'
        design: isNative() ? 'blue' : 'classic', // native default = tema biru ERPNext
        ...(saved.settings || {})
      },
      // toast sederhana
      toast: null,
      // event beforeinstallprompt (runtime, tidak dipersist) untuk install PWA
      installPrompt: null,
      // notifikasi in-app (polling Notification Log)
      notifications: [],
      notifUnread: 0
    }
  },
  getters: {
    online: (s) => s.browserOnline && !s.forceOffline,
    isLoggedIn: (s) => !!s.user
  },
  actions: {
    persist() {
      localStorage.setItem(
        LS,
        JSON.stringify({ user: this.user, forceOffline: this.forceOffline, settings: this.settings })
      )
    },
    login(email) {
      const name = (email || 'demo@globalmagicko.com').split('@')[0]
      this.user = { email: email || 'demo@globalmagicko.com', name }
      this.persist()
    },
    setUser(user) {
      this.user = user
      this.persist()
    },
    // Samakan default company/gudang dengan data master nyata bila tidak cocok.
    reconcileDefaults() {
      const m = useMaster()
      const companies = m.companyNames
      const patch = {}
      let company = this.settings.company
      const serverCompany = m.defaults && m.defaults.company
      // Perusahaan default dari server (Employee/lingkup user) berubah sejak sinkron terakhir —
      // mis. Employee dipindah perusahaan → ikuti. Bila Company terkunci, selalu ikut server.
      // Di luar itu pilihan manual user multi-perusahaan tetap dipertahankan.
      if (
        serverCompany &&
        (serverCompany !== this.settings.serverCompany || (m.defaults.company_read_only && company !== serverCompany))
      ) {
        company = serverCompany
        patch.company = serverCompany
        patch.serverCompany = serverCompany
      }
      if (companies.length && !companies.includes(company)) {
        company = serverCompany || companies[0]
        patch.company = company
      }
      const whs = m.warehousesForCompany(company)
      if (whs.length && !whs.includes(this.settings.defaultSourceWarehouse)) patch.defaultSourceWarehouse = whs[0]
      if (whs.length && !whs.includes(this.settings.defaultTargetWarehouse))
        patch.defaultTargetWarehouse = whs[Math.min(1, whs.length - 1)]
      if (Object.keys(patch).length) this.saveSettings(patch)
    },
    async logout() {
      const platform = await import('../lib/platform')
      const native = platform.isNative()
      // 1) Akhiri sesi di server. Web: hapus cookie sesi Frappe (sid); native: akhiri sesi + token.
      //    Tanpa ini, sesi cookie tetap hidup → main.js auto-login lagi dari window.stockops_user
      //    saat reload → "tidak bisa logout".
      try {
        const { call } = await import('../lib/api')
        await call('logout', {}, { post: true })
      } catch {
        // offline / sesi sudah tak ada — tetap lanjut bersihkan lokal
      }
      // 2) Bersihkan state lokal + token native.
      platform.clearToken()
      this.user = null
      this.persist()
      // 3) Web (disajikan bench): reload penuh ke halaman login Frappe. Hanya ganti route SPA
      //    tidak cukup — www page akan menyuntik user sesi lagi. /login di luar scope service
      //    worker → selalu memuat dari server sebagai Guest.
      if (!native && typeof window !== 'undefined' && window.stockops_user) {
        window.location.replace('/login?redirect-to=/stock_ops')
        return true // sedang reload penuh
      }
      return false
    },
    setForceOffline(v) {
      this.forceOffline = v
      this.persist()
      if (!v) this.autoSyncOnReconnect()
    },
    // Saat kembali online, flush outbox bila auto-sync aktif (lazy import hindari siklus).
    async autoSyncOnReconnect() {
      if (!this.online || !this.settings.autoSync || !this.isLoggedIn) return
      const { useDocs } = await import('./docs')
      const docs = useDocs()
      if (docs.pendingCount > 0) docs.syncAll()
    },
    saveSettings(patch) {
      this.settings = { ...this.settings, ...patch }
      this.persist()
      if ('theme' in patch) this.applyTheme()
      if ('design' in patch) this.applyDesign()
    },
    applyTheme() {
      const t = this.settings.theme || 'system'
      const dark = t === 'dark' || (t === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
      document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    },
    applyDesign() {
      document.documentElement.dataset.design = this.settings.design || 'classic'
    },
    // Bahasa default dari server — hanya dipakai bila user belum memilih manual.
    applyServerLang(lang) {
      if (this.settings.langUserSet) return
      if ((lang === 'id' || lang === 'en') && lang !== this.settings.lang) {
        this.saveSettings({ lang })
      }
    },
    async loadNotifications() {
      if (!this.isLoggedIn || !this.online) return
      try {
        const { getNotifications } = await import('../lib/service')
        const r = await getNotifications(20)
        this.notifications = r.items || []
        this.notifUnread = r.unread || 0
      } catch {
        // diam saja (mis. offline)
      }
    },
    async markNotificationsRead(name) {
      try {
        const { markNotificationsRead } = await import('../lib/service')
        await markNotificationsRead(name)
      } catch {
        // ignore
      }
      await this.loadNotifications()
    },
    async promptInstall() {
      if (!this.installPrompt) return false
      this.installPrompt.prompt()
      const { outcome } = await this.installPrompt.userChoice
      this.installPrompt = null
      return outcome === 'accepted'
    },
    notify(message, kind = 'info') {
      this.toast = { message, kind, id: Date.now() }
      setTimeout(() => {
        if (this.toast && Date.now() - this.toast.id >= 2400) this.toast = null
      }, 2600)
    },
    bindNetwork() {
      window.addEventListener('online', () => {
        this.browserOnline = true
        this.autoSyncOnReconnect()
      })
      window.addEventListener('offline', () => (this.browserOnline = false))
      // Migrasi nama desain lama → 3 desain saat ini (blue/classic/compact)
      const validDesigns = ['blue', 'classic', 'compact']
      if (!validDesigns.includes(this.settings.design)) {
        const map = { erpnext: 'blue', b: 'compact' }
        this.settings.design = map[this.settings.design] || 'classic'
        this.persist()
      }
      this.applyTheme()
      this.applyDesign()
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        if (this.settings.theme === 'system') this.applyTheme()
      })
    }
  }
})
