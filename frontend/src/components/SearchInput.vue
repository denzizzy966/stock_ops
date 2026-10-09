<script setup>
defineProps({ modelValue: { type: String, default: '' }, placeholder: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <div class="search">
    <span class="search-ic"><Icon name="search" /></span>
    <input
      :value="modelValue"
      :placeholder="placeholder"
      inputmode="search"
      @input="emit('update:modelValue', $event.target.value)"
    />
    <button v-if="modelValue" class="search-clear" @click="emit('update:modelValue', '')" aria-label="clear"><Icon name="close" /></button>
  </div>
</template>
