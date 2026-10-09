<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { DOC_TYPE_LIST } from '../data/mock'
import { useI18n } from '../lib/i18n'
import { useMaster } from '../stores/master'
import AppBar from '../components/AppBar.vue'

const router = useRouter()
const { t } = useI18n()
const master = useMaster()
const on = (ty) => master.menuOn(ty.key.toLowerCase())
const mrTypes = computed(() => DOC_TYPE_LIST.filter((x) => x.doctype === 'Material Request' && on(x)))
const seTypes = computed(() => DOC_TYPE_LIST.filter((x) => x.doctype === 'Stock Entry' && on(x)))
const prTypes = computed(() => DOC_TYPE_LIST.filter((x) => x.doctype === 'Purchase Receipt' && !x.isReturn && on(x)))
const retTypes = computed(() => DOC_TYPE_LIST.filter((x) => x.isReturn && on(x)))
// Quotation (penjualan) hanya untuk user yang boleh buat Quotation di server.
const qtnTypes = computed(() => (master.canQuotation ? DOC_TYPE_LIST.filter((x) => x.isQuotation && on(x)) : []))
</script>

<template>
  <AppBar :title="t('create.title')" />
  <div class="content">
    <div v-if="mrTypes.length" class="section-title">{{ t('docType.groupMR') }}</div>
    <button
      v-for="ty in mrTypes"
      :key="ty.key"
      class="list-item"
      style="width: 100%; text-align: left; border: 0; cursor: pointer"
      @click="router.push(`/form/${ty.key}`)"
    >
      <span class="lead-icon" :style="{ background: ty.color }"><Icon :name="ty.icon" /></span>
      <div class="grow">
        <div style="font-weight: 700">{{ t('docType.' + ty.key) }}</div>
        <div class="tiny muted">{{ ty.doctype }} · {{ ty.meta }}</div>
      </div>
      <span style="font-size: 22px; color: var(--muted)">›</span>
    </button>

    <div v-if="seTypes.length" class="section-title">{{ t('docType.groupSE') }}</div>
    <button
      v-for="ty in seTypes"
      :key="ty.key"
      class="list-item"
      style="width: 100%; text-align: left; border: 0; cursor: pointer"
      @click="router.push(`/form/${ty.key}`)"
    >
      <span class="lead-icon" :style="{ background: ty.color }"><Icon :name="ty.icon" /></span>
      <div class="grow">
        <div style="font-weight: 700">{{ t('docType.' + ty.key) }}</div>
        <div class="tiny muted">{{ ty.doctype }} · {{ ty.meta }}</div>
      </div>
      <span style="font-size: 22px; color: var(--muted)">›</span>
    </button>

    <div v-if="prTypes.length" class="section-title">{{ t('docType.groupPR') }}</div>
    <button
      v-for="ty in prTypes"
      :key="ty.key"
      class="list-item"
      style="width: 100%; text-align: left; border: 0; cursor: pointer"
      @click="router.push(`/form/${ty.key}`)"
    >
      <span class="lead-icon" :style="{ background: ty.color }"><Icon :name="ty.icon" /></span>
      <div class="grow">
        <div style="font-weight: 700">{{ t('docType.' + ty.key) }}</div>
        <div class="tiny muted">{{ ty.doctype }} · {{ ty.meta }}</div>
      </div>
      <span style="font-size: 22px; color: var(--muted)">›</span>
    </button>

    <div v-if="retTypes.length" class="section-title">{{ t('docType.groupRET') }}</div>
    <button
      v-for="ty in retTypes"
      :key="ty.key"
      class="list-item"
      style="width: 100%; text-align: left; border: 0; cursor: pointer"
      @click="router.push('/return')"
    >
      <span class="lead-icon" :style="{ background: ty.color }"><Icon :name="ty.icon" /></span>
      <div class="grow">
        <div style="font-weight: 700">{{ t('docType.' + ty.key) }}</div>
        <div class="tiny muted">{{ ty.doctype }} · {{ ty.meta }}</div>
      </div>
      <span style="font-size: 22px; color: var(--muted)">›</span>
    </button>

    <div v-if="qtnTypes.length" class="section-title">{{ t('docType.groupQTN') }}</div>
    <button
      v-for="ty in qtnTypes"
      :key="ty.key"
      class="list-item"
      style="width: 100%; text-align: left; border: 0; cursor: pointer"
      @click="router.push(`/form/${ty.key}`)"
    >
      <span class="lead-icon" :style="{ background: ty.color }"><Icon :name="ty.icon" /></span>
      <div class="grow">
        <div style="font-weight: 700">{{ t('docType.' + ty.key) }}</div>
        <div class="tiny muted">{{ ty.doctype }} · {{ ty.meta }}</div>
      </div>
      <span style="font-size: 22px; color: var(--muted)">›</span>
    </button>
  </div>
</template>
