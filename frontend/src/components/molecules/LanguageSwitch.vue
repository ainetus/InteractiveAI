<template>
  <div class="cab-language" role="radiogroup" :aria-label="$t('language.label')">
    <Languages :size="16" />
    <button
      v-for="language of SUPPORT_LOCALES"
      :key="language"
      type="button"
      role="radio"
      :aria-checked="language === current"
      :title="$t(`language.${language}`)"
      :class="{ selected: language === current }"
      @click="setLanguage(language)">
      {{ language.toUpperCase() }}
    </button>
  </div>
</template>
<script setup lang="ts">
import { Languages } from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { setLanguage, SUPPORT_LOCALES } from '@/plugins/i18n'

const { locale } = useI18n()
/** 'fr' in 'fr-Railway' */
const current = computed(() => locale.value.slice(0, 2))
</script>
<style scoped lang="scss">
.cab-language {
  display: flex;
  align-items: center;
  gap: calc(var(--unit) * 0.5);
  color: var(--color-grey-600);

  button {
    cursor: pointer;
    padding: calc(var(--unit) * 0.25) var(--spacing-1);
    border: 1px solid var(--color-grey-400);
    border-radius: var(--radius-circular);
    background: var(--color-background);
    color: var(--color-text);
    font: inherit;
    font-size: 0.8rem;
    font-weight: bold;

    &:hover {
      border-color: var(--color-primary);
    }
    &.selected {
      background: var(--color-primary);
      border-color: var(--color-primary);
      color: var(--color-text-inverted);
    }
  }
}
</style>
