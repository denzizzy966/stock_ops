<script setup>
import { computed } from 'vue'
import { useDocs } from '../stores/docs'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'

const docs = useDocs()
const master = useMaster()
const { t } = useI18n()
const pending = computed(() => docs.pendingCount)
const showBalance = computed(() => master.menuOn('stock_balance'))
const showMovement = computed(() => master.menuOn('movement'))
const showDocs = computed(() => master.menuOn('documents'))
const showCreate = computed(() => ['mr', 'pr', 'se_in', 'se_out', 'se_transfer'].some((k) => master.menuOn(k)))
</script>

<template>
  <!-- ===== Navigasi 6 tab (semua desain) ===== -->
  <nav class="tabbar">
    <router-link to="/" :class="{ active: $route.name === 'home' }">
      <span class="ic"><Icon name="home" /></span><span class="lbl">{{ t('nav.home') }}</span>
    </router-link>
    <router-link v-if="showBalance" to="/balance" :class="{ active: $route.name === 'balance' }">
      <span class="ic"><Icon name="warehouse" /></span><span class="lbl">{{ t('nav.balance') }}</span>
    </router-link>
    <router-link v-if="showMovement" to="/movement" :class="{ active: $route.name === 'movement' }">
      <span class="ic"><Icon name="movement" /></span><span class="lbl">{{ t('nav.movement') }}</span>
    </router-link>
    <router-link v-if="showCreate" to="/create" :class="{ active: $route.name === 'create' }">
      <span class="ic"><Icon name="plus" /></span><span class="lbl">{{ t('nav.create') }}</span>
    </router-link>
    <router-link v-if="showDocs" to="/docs" :class="{ active: $route.name === 'docs' }">
      <span class="ic"><Icon name="list" /></span><span class="lbl">{{ t('nav.list') }}</span>
    </router-link>
    <router-link to="/settings" :class="{ active: $route.name === 'settings' || $route.name === 'sync' || $route.name === 'reports' }">
      <span class="ic"><Icon name="settings" /></span><span class="lbl">{{ t('nav.settings') }}</span>
      <span v-if="pending" class="badge">{{ pending }}</span>
    </router-link>
  </nav>
</template>
