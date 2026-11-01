// Lapisan akses Frappe REST.
// - Web di-serve bench: same-origin (/api/...) + cookie sesi + CSRF.
// - Web dev (vite): same-origin diproksikan + token disuntik proxy Node.
// - Native (Capacitor): base URL absolut (ERPNext) + Authorization token; CapacitorHttp
//   mem-patch fetch → lewat native → tidak kena CORS.
import { apiBase, getToken } from './platform'

// CSRF token disuntik oleh www page Frappe (window.csrf_token). Di dev/native kosong.
function csrfToken() {
  const t = typeof window !== 'undefined' ? window.csrf_token : ''
  if (!t || t.includes('{{')) return ''
  return t
}

// Header auth: native pakai token; web pakai CSRF (untuk POST) + cookie sesi.
function authHeaders(isPost) {
  const h = {}
  const tok = getToken()
  if (tok) {
    h.Authorization = tok
  } else if (isPost) {
    const c = csrfToken()
    if (c) h['X-Frappe-CSRF-Token'] = c
  }
  return h
}

class ApiError extends Error {
  constructor(message, status, data) {
    super(message)
    this.status = status
    this.data = data
  }
}

function serverMessages(json) {
  try {
    const msgs = json._server_messages ? JSON.parse(json._server_messages) : []
    return msgs.map((m) => (typeof m === 'string' ? JSON.parse(m).message : m.message)).join(' · ')
  } catch {
    return ''
  }
}

async function handle(res) {
  let json = null
  const text = await res.text()
  try {
    json = text ? JSON.parse(text) : null
  } catch {
    json = null
  }
  if (!res.ok) {
    const msg =
      (json && (serverMessages(json) || json.exception || json.message)) ||
      `HTTP ${res.status}`
    throw new ApiError(typeof msg === 'string' ? msg : 'Request gagal', res.status, json)
  }
  return json
}

// Panggil whitelisted method. GET untuk read, POST untuk aksi.
export async function call(method, params = {}, { post = false } = {}) {
  let url = `${apiBase()}/api/method/${method}`
  const opts = { method: post ? 'POST' : 'GET', headers: { Accept: 'application/json', ...authHeaders(post) } }
  if (post) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(params)
  } else {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null) continue // jangan kirim "undefined"/"null" sebagai nilai filter
      qs.append(k, typeof v === 'object' ? JSON.stringify(v) : v)
    }
    const s = qs.toString()
    if (s) url += `?${s}`
  }
  const json = await handle(await fetch(url, opts))
  return json ? json.message : null
}

// Whitelisted method yang mengembalikan file (response type "download") → Blob.
export async function fetchBlob(method, params = {}) {
  const qs = new URLSearchParams(params).toString()
  const res = await fetch(`${apiBase()}/api/method/${method}${qs ? `?${qs}` : ''}`, { headers: authHeaders(false) })
  if (!res.ok) await handle(res) // lempar ApiError dengan pesan server
  return res.blob()
}

// List dokumen via resource API.
export async function list(doctype, { fields, filters, limit = 0, order_by, parent } = {}) {
  const qs = new URLSearchParams()
  if (fields) qs.append('fields', JSON.stringify(fields))
  if (filters) qs.append('filters', JSON.stringify(filters))
  if (order_by) qs.append('order_by', order_by)
  qs.append('limit_page_length', String(limit))
  if (parent) qs.append('parent', parent)
  const json = await handle(
    await fetch(`${apiBase()}/api/resource/${encodeURIComponent(doctype)}?${qs.toString()}`, { headers: authHeaders(false) })
  )
  return json ? json.data : []
}

export async function getDoc(doctype, name) {
  const json = await handle(
    await fetch(`${apiBase()}/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`, { headers: authHeaders(false) })
  )
  return json ? json.data : null
}

// Upload satu foto (Blob) & lampirkan ke dokumen.
export async function uploadFile(blob, { doctype, docname, isPrivate = true, filename = 'photo.jpg' }) {
  const fd = new FormData()
  fd.append('file', blob, filename)
  fd.append('is_private', isPrivate ? '1' : '0')
  fd.append('folder', 'Home/Attachments')
  fd.append('doctype', doctype)
  fd.append('docname', docname)
  const json = await handle(
    await fetch(`${apiBase()}/api/method/upload_file`, { method: 'POST', body: fd, headers: authHeaders(true) })
  )
  return json ? json.message : null
}

export { ApiError }
