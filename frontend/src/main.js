import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/main.css'
import { useApp } from './stores/app'
import { useMaster } from './stores/master'

import Icon from './components/Icon.vue'

const app = createApp(App)
app.use(createPinia())
app.use(router)
// Ikon SVG (Font Awesome Free) tersedia di semua template sebagai <Icon name="…" />
app.component('Icon', Icon)

// mulai pantau status jaringan + tema
const appStore = useApp()
appStore.bindNetwork()

// Saat disajikan bench, www page menyuntik user sesi → auto-login (lewati layar login).
const injectedUser = typeof window !== 'undefined' ? window.stockops_user : ''
const servedByBench = !!injectedUser && injectedUser !== 'Guest' && !injectedUser.includes('{{')
if (servedByBench) {
  appStore.setUser({ email: injectedUser, name: injectedUser })
} else if (injectedUser === 'Guest' && appStore.user) {
  // Halaman disajikan bench untuk tamu (sesi habis / sudah keluar) → user lokal tidak berlaku lagi,
  // supaya layar login PWA yang tampil (bukan beranda dengan data basi).
  appStore.setUser(null)
}

app.mount('#app')

// Splash (index.html) dilepas setelah rute pertama tampil.
router.isReady().then(() => {
  const s = document.getElementById('splash')
  if (!s) return
  s.classList.add('hide')
  setTimeout(() => s.remove(), 400)
})

// Tangkap event install PWA (Android/Chrome) agar bisa dipicu dari tombol di Setelan.
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault()
  appStore.installPrompt = e
})
window.addEventListener('appinstalled', () => {
  appStore.installPrompt = null
})

// Service worker (PWA installable + offline app-shell) hanya saat disajikan bench.
// Scope "/stock_ops" TANPA slash akhir: beberapa server (proxy Docker) membalas "/stock_ops/" dengan
// redirect absolut ke port internal (mis. :8080) → app terpasang gagal dibuka. SW lama (scope
// "/stock_ops/") dilepas.
if (servedByBench && 'serviceWorker' in navigator) {
  navigator.serviceWorker
    .getRegistrations()
    .then((regs) => regs.filter((r) => new URL(r.scope).pathname === '/stock_ops/').forEach((r) => r.unregister()))
    .catch(() => {})
  navigator.serviceWorker.register('/stock_ops_sw.js', { scope: '/stock_ops' }).catch(() => {})
}

// Jika sudah login & online, segarkan master data di latar (juga jadi cache offline).
if (appStore.isLoggedIn && appStore.online) {
  const master = useMaster()
  master
    .load()
    .then(() => appStore.reconcileDefaults())
    .catch(() => {})
}

// Notifikasi in-app: poll saat login, tiap 60 detik, dan saat tab kembali aktif.
if (appStore.isLoggedIn) {
  appStore.loadNotifications()
  setInterval(() => appStore.loadNotifications(), 60000)
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) appStore.loadNotifications()
  })
}
