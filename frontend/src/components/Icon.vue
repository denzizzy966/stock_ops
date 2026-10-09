<script setup>
import { computed } from 'vue'
import { ICONS } from '../lib/icons'

// Ikon SVG (Font Awesome Free) — warna mengikuti teks (currentColor), ukuran mengikuti font-size.
const props = defineProps({
  name: { type: String, required: true },
  spin: { type: Boolean, default: false }
})
const def = computed(() => (ICONS[props.name] || ICONS.question).icon) // [w, h, ligatures, unicode, path]
const viewBox = computed(() => `0 0 ${def.value[0]} ${def.value[1]}`)
const paths = computed(() => (Array.isArray(def.value[4]) ? def.value[4] : [def.value[4]]))
</script>

<template>
  <svg class="ico" :class="{ 'ico-spin': spin }" :viewBox="viewBox" aria-hidden="true" focusable="false">
    <path v-for="(d, i) in paths" :key="i" :d="d" fill="currentColor" />
  </svg>
</template>
