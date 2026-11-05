import { createRouter, createWebHashHistory } from 'vue-router'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'

// route name -> menu key (Stock Ops Settings). Route tanpa entri = selalu boleh.
const ROUTE_MENU = {
  balance: 'stock_balance',
  movement: 'movement',
  docs: 'documents',
  lookup: 'scan',
  low: 'low_stock',
  'quick-transfer': 'transfer',
  opname: 'opname',
  return: 'ret',
  approvals: 'approvals'
}
const RTP_ROUTES = ['rtp-list', 'rtp-new', 'rtp-detail', 'rtp-edit']
const HR_ROUTES = ['hr-list', 'hr-new', 'hr-detail', 'hr-edit']
const CREATE_KEYS = ['mr', 'pr', 'se_in', 'se_out', 'se_transfer', 'grn', 'ret']

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/', name: 'home', component: () => import('../views/HomeView.vue'), meta: { tab: 'home' } },
  { path: '/docs', name: 'docs', component: () => import('../views/DocListView.vue'), meta: { tab: 'docs' } },
  { path: '/create', name: 'create', component: () => import('../views/CreateView.vue'), meta: { tab: 'create' } },
  { path: '/sync', name: 'sync', component: () => import('../views/SyncView.vue'), meta: { tab: 'settings' } },
  { path: '/settings', name: 'settings', component: () => import('../views/SettingsView.vue'), meta: { tab: 'settings' } },
  { path: '/reports', name: 'reports', component: () => import('../views/ReportsView.vue'), meta: { tab: 'settings' } },
  { path: '/notifications', name: 'notifications', component: () => import('../views/NotificationsView.vue'), meta: { tab: 'home' } },
  { path: '/balance', name: 'balance', component: () => import('../views/StockBalanceView.vue'), meta: { tab: 'home' } },
  { path: '/movement', name: 'movement', component: () => import('../views/StockMovementView.vue'), meta: { tab: 'home' } },
  { path: '/lookup', name: 'lookup', component: () => import('../views/ItemLookupView.vue'), meta: { tab: 'home' } },
  { path: '/item/:code', name: 'item', component: () => import('../views/ItemDetailView.vue'), meta: { tab: 'home' } },
  { path: '/low', name: 'low', component: () => import('../views/LowStockView.vue'), meta: { tab: 'home' } },
  { path: '/quick-transfer', name: 'quick-transfer', component: () => import('../views/QuickTransferView.vue'), meta: { tab: 'home' } },
  { path: '/opname', name: 'opname', component: () => import('../views/OpnameView.vue'), meta: { tab: 'home' } },
  { path: '/form/:type', name: 'form', component: () => import('../views/DocFormView.vue') },
  { path: '/return', name: 'return', component: () => import('../views/ReturnFormView.vue') },
  { path: '/approvals', name: 'approvals', component: () => import('../views/ApprovalsView.vue'), meta: { tab: 'home' } },
  { path: '/rtp', name: 'rtp-list', component: () => import('../views/RtpListView.vue'), meta: { tab: 'home' } },
  { path: '/rtp/new', name: 'rtp-new', component: () => import('../views/RtpFormView.vue'), meta: { tab: 'home' } },
  { path: '/rtp/:name/edit', name: 'rtp-edit', component: () => import('../views/RtpFormView.vue'), meta: { tab: 'home' } },
  { path: '/rtp/:name', name: 'rtp-detail', component: () => import('../views/RtpDetailView.vue'), meta: { tab: 'home' } },
  // Menu HR: kind = claim (Expense Claim) | advance (Employee Advance)
  { path: '/hr/:kind(claim|advance)', name: 'hr-list', component: () => import('../views/HrListView.vue'), meta: { tab: 'home' } },
  { path: '/hr/:kind(claim|advance)/new', name: 'hr-new', component: () => import('../views/HrFormView.vue'), meta: { tab: 'home' } },
  { path: '/hr/:kind(claim|advance)/:name/edit', name: 'hr-edit', component: () => import('../views/HrFormView.vue'), meta: { tab: 'home' } },
  { path: '/hr/:kind(claim|advance)/:name', name: 'hr-detail', component: () => import('../views/HrDetailView.vue'), meta: { tab: 'home' } },
  { path: '/doc/:localId', name: 'detail', component: () => import('../views/DocDetailView.vue') },
  { path: '/sdoc/:doctype/:name', name: 'server-doc', component: () => import('../views/ServerDocView.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

router.beforeEach(async (to) => {
  const app = useApp()
  if (!to.meta.public && !app.isLoggedIn) return { name: 'login' }
  if (to.name === 'login' && app.isLoggedIn) return { name: 'home' }
  // Blokir akses langsung (URL) ke menu yang dimatikan di Stock Ops Settings.
  if (app.isLoggedIn) {
    const master = useMaster()
    const key = ROUTE_MENU[to.name]
    if (key && !master.menuOn(key)) return { name: 'home' }
    if (RTP_ROUTES.includes(to.name)) {
      // caps.rtp baru ada setelah bootstrap; jangan putuskan "tidak punya akses" sebelum dimuat.
      if (!master.loadedAt && app.online) await master.ensureLoaded().catch(() => {})
      if (!master.rtpOn) return { name: 'home' }
    }
    if (HR_ROUTES.includes(to.name)) {
      if (!master.loadedAt && app.online) await master.ensureLoaded().catch(() => {})
      if (!master.hrOn(to.params.kind)) return { name: 'home' }
    }
    if (to.name === 'create' && !CREATE_KEYS.some((k) => master.menuOn(k))) return { name: 'home' }
    if (to.name === 'form' && to.params.type && !master.menuOn(String(to.params.type).toLowerCase())) return { name: 'home' }
  }
})

export default router
