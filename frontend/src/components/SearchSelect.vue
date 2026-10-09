<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from '../lib/i18n'

// Picker dropdown yang bisa dicari (select2-style) — WAJIB dipakai untuk SEMUA dropdown aplikasi
// (perusahaan, supplier, gudang, tujuan, satuan, …), bukan <select> bawaan: daftar nyata bisa
// ratusan opsi (supplier) dan staf di ponsel perlu mengetik untuk menemukannya.
const props = defineProps({
  modelValue: { type: String, default: '' },
  options: { type: Array, default: () => [] }, // daftar string
  placeholder: { type: String, default: '—' },
  disabled: { type: Boolean, default: false },
  clearable: { type: Boolean, default: false }, // tampilkan opsi "—" untuk mengosongkan (field opsional)
  searchPlaceholder: { type: String, default: '' },
  emptyText: { type: String, default: '' },
  compact: { type: Boolean, default: false } // gaya kecil (mis. pilihan Satuan di baris item)
})
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()

const open = ref(false)
const q = ref('')
const root = ref(null)
const searchEl = ref(null)

const filtered = computed(() => {
  const s = q.value.trim().toLowerCase()
  if (!s) return props.options
  return props.options.filter((o) => String(o).toLowerCase().includes(s))
})

function toggle() {
  if (props.disabled) return
  open.value = !open.value
  if (open.value) {
    q.value = ''
    nextTick(() => searchEl.value && searchEl.value.focus())
  }
}
function pick(o) {
  emit('update:modelValue', o)
  open.value = false
}
function onDocClick(e) {
  if (root.value && !root.value.contains(e.target)) open.value = false
}
onMounted(() => document.addEventListener('click', onDocClick, true))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick, true))
</script>

<template>
  <div class="wh-select" :class="{ compact }" ref="root">
    <button type="button" class="wh-control" :class="{ disabled }" :disabled="disabled" @click="toggle">
      <span class="wh-value" :class="{ ph: !modelValue }">{{ modelValue || placeholder }}</span>
      <span class="wh-caret">▾</span>
    </button>
    <div v-if="open" class="wh-panel">
      <input
        ref="searchEl"
        v-model="q"
        class="wh-search"
        type="text"
        :placeholder="searchPlaceholder || t('form.search')"
        @keydown.esc.prevent="open = false"
      />
      <div class="wh-list">
        <button v-if="clearable && !q" type="button" class="wh-opt muted-opt" :class="{ active: !modelValue }" @click="pick('')">—</button>
        <button
          v-for="o in filtered"
          :key="o"
          type="button"
          class="wh-opt"
          :class="{ active: o === modelValue }"
          @click="pick(o)"
        >
          {{ o }}
        </button>
        <div v-if="!filtered.length" class="wh-empty">{{ emptyText || t('form.searchEmpty') }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wh-select { position: relative; }
.wh-control {
  width: 100%; display: flex; align-items: center; gap: 8px;
  border: 1px solid var(--line); background: var(--input-bg); color: var(--ink);
  border-radius: 12px; padding: 12px 14px; font-size: 16px; text-align: left; cursor: pointer;
}
.wh-control.disabled { opacity: 0.6; cursor: not-allowed; }
.wh-value { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.wh-value.ph { color: var(--muted); }
.wh-caret { color: var(--muted); font-size: 12px; flex: none; }
.wh-panel {
  position: absolute; z-index: 50; top: calc(100% + 4px); left: 0; right: 0;
  background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  box-shadow: var(--shadow); padding: 8px; overflow: hidden;
}
.wh-search {
  width: 100%; border: 1px solid var(--line); background: var(--input-bg); color: var(--ink);
  border-radius: 10px; padding: 10px 12px; font-size: 15px; margin-bottom: 6px;
}
.wh-search:focus { outline: 2px solid var(--brand); border-color: transparent; }
.wh-list { max-height: 240px; overflow-y: auto; -webkit-overflow-scrolling: touch; }
.wh-opt {
  display: block; width: 100%; text-align: left; border: 0; background: transparent; color: var(--ink);
  padding: 11px 10px; border-radius: 8px; font-size: 15px; cursor: pointer;
}
.wh-opt:hover { background: var(--input-bg); }
.wh-opt.active { background: var(--brand); color: var(--brand-ink, #fff); font-weight: 600; }
.wh-opt.muted-opt { color: var(--muted); }
.wh-empty { padding: 14px 10px; color: var(--muted); font-size: 14px; text-align: center; }

/* Gaya ringkas (Satuan di baris item): tombol kecil berbingkai brand, panel lebih lebar dari tombol. */
.compact { display: inline-block; min-width: 96px; }
.compact .wh-control {
  border-color: var(--brand); border-radius: 10px; padding: 9px 12px; min-height: 42px;
  font-size: 15px; font-weight: 700;
}
.compact .wh-caret { color: var(--brand); }
.compact .wh-panel { right: auto; min-width: 190px; }
</style>
