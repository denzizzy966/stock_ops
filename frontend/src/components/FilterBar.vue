<script setup>
import { ref, useSlots } from 'vue'

const props = defineProps({
  count: { type: Number, default: 0 }, // jumlah filter aktif (badge)
  collapsible: { type: Boolean, default: true }
})
const slots = useSlots()
const open = ref(true)
</script>

<template>
  <div class="toolbar">
    <div class="row" style="gap: 8px">
      <div class="grow" style="min-width: 0"><slot name="bar" /></div>
      <button v-if="slots.default && collapsible" class="filter-btn" :class="{ on: open }" @click="open = !open" aria-label="filter">
        <span class="fb-ic"><Icon name="filter" /></span>
        <span v-if="count" class="fb-badge">{{ count }}</span>
        <span class="fb-chev">{{ open ? '▲' : '▼' }}</span>
      </button>
    </div>
    <div v-show="slots.default && (open || !collapsible)" class="filter-body"><slot /></div>
  </div>
</template>
