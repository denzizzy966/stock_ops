<script setup>
import { ref, reactive, onBeforeUnmount } from 'vue'
import { fileToResizedBlob, uuid } from '../lib/util'
import { putPhoto, deletePhoto } from '../lib/idb'
import { useApp } from '../stores/app'
import { useI18n } from '../lib/i18n'

// v-model: array of { id, name, uploaded } — Blob disimpan di IndexedDB (keyed by id).
const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  localId: { type: String, required: true }
})
const emit = defineEmits(['update:modelValue'])
const app = useApp()
const { t } = useI18n()
const fileInput = ref(null)
const busy = ref(false)
const urls = reactive({}) // id -> objectURL (preview)

function pick() {
  fileInput.value?.click()
}

async function onFiles(e) {
  const files = Array.from(e.target.files || [])
  if (!files.length) return
  busy.value = true
  try {
    const next = [...props.modelValue]
    for (const f of files) {
      const blob = await fileToResizedBlob(f)
      const id = uuid()
      const name = (f.name || 'foto').replace(/\.[^.]+$/, '') + '.jpg'
      await putPhoto({ id, localId: props.localId, blob, name })
      urls[id] = URL.createObjectURL(blob)
      next.push({ id, name, uploaded: false })
    }
    emit('update:modelValue', next)
    app.notify(t('toast.photosAdded', { n: files.length }), 'success')
  } catch {
    app.notify(t('toast.photoFail'), 'error')
  } finally {
    busy.value = false
    e.target.value = ''
  }
}

async function remove(id) {
  await deletePhoto(id)
  if (urls[id]) {
    URL.revokeObjectURL(urls[id])
    delete urls[id]
  }
  emit('update:modelValue', props.modelValue.filter((p) => p.id !== id))
}

onBeforeUnmount(() => {
  Object.values(urls).forEach((u) => URL.revokeObjectURL(u))
})
</script>

<template>
  <div>
    <div class="photo-grid">
      <div v-for="p in modelValue" :key="p.id" class="ph">
        <img :src="urls[p.id]" alt="" />
        <button class="x" @click="remove(p.id)"><Icon name="close" /></button>
      </div>
      <button class="photo-add" @click="pick" :disabled="busy">
        <span class="big"><Icon :name="busy ? 'loading' : 'camera'" :spin="busy" /></span>
        {{ busy ? t('form.processing') : t('form.addPhoto') }}
      </button>
    </div>
    <input ref="fileInput" type="file" accept="image/*" capture="environment" multiple hidden @change="onFiles" />
    <p class="tiny muted mt8">
      {{ t('form.photoHint', { vis: app.settings.privatePhotos ? 'private' : 'public' }) }}
    </p>
  </div>
</template>
