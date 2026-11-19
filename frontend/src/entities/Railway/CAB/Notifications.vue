<template>
  <Notifications entity="Railway" :sections>
    <template #severity="{ card }">
      <!-- a card that opens a decision (F-27) -->
      <span
        v-if="decisionMark(card.data.metadata, context)"
        class="railway-card-decision"
        :class="decisionMark(card.data.metadata, context)"
        :data-decision="decisionMark(card.data.metadata, context)">
        {{
          decisionMark(card.data.metadata, context) === 'open'
            ? `⚠ ${$t('Railway.decision.mark')}`
            : `✓ ${$t('Railway.decision.decided')}`
        }}
      </span>
      {{
        $t(`card.event_type.${card.data.metadata.event_type}`) !==
        `card.event_type.${card.data.metadata.event_type}`
          ? $t(`card.event_type.${card.data.metadata.event_type}`)
          : card.data.metadata.event_type
      }}
    </template>
    <template #actions="{ card, deletion, hasBeenAcknowledged }">
      <Tooltip>
        <template #tooltip>
          {{ $t('card.actions.move_user.tooltip') }}
        </template>
        <Button size="small" color="secondary">
          <MoveRight :height="12" />
          <User :height="12" />
        </Button>
      </Tooltip>
      <Tooltip v-if="!hasBeenAcknowledged">
        <template #tooltip>{{ $t('card.actions.delete.tooltip') }}</template>
        <Button size="small" color="secondary" @click.stop="deletion(card)">
          <Inbox :height="12" />
        </Button>
      </Tooltip>
    </template>
  </Notifications>
</template>
<script setup lang="ts">
import '@/entities/Railway/i18n'

import { Inbox, MoveRight, User } from 'lucide-vue-next'
import { computed } from 'vue'

import Button from '@/components/atoms/Button.vue'
import Tooltip from '@/components/atoms/Tooltip.vue'
import Notifications from '@/components/organisms/CAB/Notifications.vue'
import { decisionMark } from '@/entities/Railway/feed/decisionMark'
import { sections } from '@/entities/Railway/feed/sections'
import { useServicesStore } from '@/stores/services'

const servicesStore = useServicesStore()
const context = computed(() => servicesStore.context('Railway')?.data)
</script>
<style lang="scss">
.railway-card-decision {
  margin-right: var(--spacing-1);
  padding: 1px var(--spacing-1);
  border-radius: 4px;
  font-weight: 600;
  white-space: nowrap;
  &.open {
    background: #ffe3e3;
    color: var(--color-red-500);
  }
  &.decided {
    background: var(--color-grey-200);
    color: var(--color-grey-600);
  }
}
</style>
