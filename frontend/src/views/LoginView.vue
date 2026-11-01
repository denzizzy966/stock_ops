<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { isNative, getServerUrl } from '../lib/platform'
import { nativeLogin } from '../lib/service'

const app = useApp()
const master = useMaster()
const router = useRouter()
const { t } = useI18n()

const native = isNative()
// Disajikan bench (/stock_ops) → login ke sesi ERPNext lewat /api/method/login. Selain itu: dev/mock.
const bench = !native && typeof window.stockops_user === 'string' && !window.stockops_user.includes('{{')
const serverUrl = ref(getServerUrl() || 'https://erp.halosocia.my.id')
const email = ref(native || bench ? '' : 'demo@globalmagicko.com')
const password = ref(native || bench ? '' : 'demo')
const loading = ref(false)
const showPw = ref(false)
const err = ref('')

async function benchLogin() {
  if (!email.value.trim() || !password.value) {
    err.value = t('login.fill')
    return
  }
  err.value = ''
  let res
  try {
    res = await fetch('/api/method/login', {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ usr: email.value.trim(), pwd: password.value }),
      credentials: 'same-origin'
    })
  } catch {
    err.value = t('login.noServer')
    return
  }
  const j = await res.json().catch(() => ({}))
  if (res.ok && j.verification) {
    // Akun dengan verifikasi 2 langkah → halaman login ERPNext (mendukung OTP).
    window.location.href = '/login?redirect-to=/stock_ops'
    return
  }
  if (res.ok) {
    // Muat ulang penuh (bukan ganti #hash) → halaman membawa sesi + CSRF token user baru.
    window.history.replaceState(null, '', '/stock_ops')
    window.location.reload()
    return
  }
  err.value = res.status === 401 ? t('login.wrong') : res.status === 429 ? t('login.tooMany') : t('login.failed', { n: res.status })
}

async function doLogin() {
  loading.value = true
  try {
    if (bench) return await benchLogin()
    let b
    if (native) {
      // App: login user/password → token → simpan, lalu ambil master pakai token.
      const m = await nativeLogin(serverUrl.value, email.value, password.value)
      b = await master.load()
      app.setUser({ email: m.user, name: m.full_name || m.user })
    } else {
      // Web (di-serve bench / proxy dev): sesi/cookie atau token proxy.
      b = await master.load()
      app.setUser({
        email: email.value || (b.user && b.user.name) || 'user',
        name: (b.user && b.user.full_name) || (email.value || 'user').split('@')[0]
      })
    }
    app.reconcileDefaults()
    app.notify(t('toast.loginOk'), 'success')
    router.push('/')
  } catch (e) {
    app.notify(e && e.message ? e.message : 'Gagal terhubung ke server', 'error')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <img class="login-logo" src="/rmi-logo.png" alt="Real Magick Indonesia" style="background: rgba(255,255,255,.92); border-radius: 18px; padding: 14px" />
    <h1 style="text-align: center; margin: 0 0 4px">Stock Ops</h1>
    <p style="text-align: center; opacity: 0.85; margin: 0 0 22px; font-size: 14px">{{ t('login.subtitle') }}</p>

    <div class="login-card">
      <div v-if="native" class="field">
        <label>{{ t('login.server') }}</label>
        <input v-model="serverUrl" type="url" inputmode="url" autocapitalize="off" placeholder="https://erp.perusahaan.com" />
      </div>
      <div class="field">
        <label>{{ native ? t('login.userId') : t('login.email') }}</label>
        <input v-model="email" type="text" autocapitalize="off" autocomplete="username" placeholder="email / username" />
      </div>
      <div class="field">
        <label>{{ t('login.password') }}</label>
        <div class="pw">
          <input v-model="password" :type="showPw ? 'text' : 'password'" autocomplete="current-password" placeholder="••••••" @keyup.enter="doLogin" />
          <button type="button" class="eye" :aria-label="showPw ? 'Sembunyikan password' : 'Tampilkan password'" @click="showPw = !showPw"><Icon :name="showPw ? 'eyeoff' : 'eye'" /></button>
        </div>
      </div>
      <div v-if="err" class="login-err" role="alert">{{ err }}</div>
      <button class="btn brand block" :disabled="loading" @click="doLogin">
        {{ loading ? '…' : t('login.signIn') }}
      </button>
      <template v-if="bench">
        <a class="tiny muted forgot" href="/login#forgot">{{ t('login.forgot') }}</a>
      </template>
      <p v-else-if="!native" class="tiny muted mt12" style="text-align: center">{{ t('login.mockNote') }}</p>
      <p v-else class="tiny muted mt12" style="text-align: center">{{ t('login.nativeNote') }}</p>
    </div>
    <p class="login-foot">© Real Magick Indonesia · ERPNext</p>
  </div>
</template>

<style scoped>
.pw { position: relative; }
.pw input { padding-right: 48px; }
.eye { position: absolute; right: 4px; top: 50%; transform: translateY(-50%); border: 0; background: none; color: var(--muted); width: 40px; height: 40px; font-size: 17px; }
.login-err { background: color-mix(in srgb, var(--danger, #dc2626) 12%, var(--card)); color: var(--danger, #dc2626); border-radius: 10px; padding: 10px 12px; font-size: 13px; font-weight: 600; margin-bottom: 12px; }
.forgot { display: block; text-align: center; margin-top: 14px; }
.login-foot { text-align: center; font-size: 11px; opacity: .55; margin: 18px 0 0; letter-spacing: .05em; }
</style>
