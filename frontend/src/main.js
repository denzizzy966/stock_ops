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
}

app.mount('#app')

// Tangkap event install PWA (Android/Chrome) agar bisa dipicu dari tombol di Setelan.
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault()
  appStore.installPrompt = e
})
window.addEventListener('appinstalled', () => {
  appStore.installPrompt = null
})

// Service worker (PWA installable + offline app-shell) hanya saat disajikan bench di /stock_ops/.
if (servedByBench && 'serviceWorker' in navigator) {
  navigator.serviceWorker.register('/stock_ops/sw.js', { scope: '/stock_ops/' }).catch(() => {})
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
