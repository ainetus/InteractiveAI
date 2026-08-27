<template>
  <Context
    :tabs="[
      $t('cab.tab.map'),
      'ZWL'
    ]">
    <FlatlandMap v-if="appStore.tab.context === 0" />
    <div v-if="appStore.tab.context === 1" style="padding: 16px; color: #ccc;">
      ZWL — coming soon
    </div>
  </Context>
</template>

<script setup lang="ts">
import Context from '@/components/organisms/CAB/Context.vue'
import FlatlandMap from './FlatlandMap.vue'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
</script>