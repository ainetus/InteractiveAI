<template>
  <!-- In the simulator's runs the shared feed does not ask "Event ended, close the notifications?"
       when a card ends (applying a decision sets it to ND): the run goes on meanwhile, and the
       card stays as the record of the decision (F-32). The geographic map (standalone mode, or a
       context without infra) keeps the question. -->
  <Notifications entity="Railway" :sections :autoclose="!simulatorRun">
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
import { standalone } from '@/entities/Railway/loader'
import { useCardsStore } from '@/stores/cards'
import { useServicesStore } from '@/stores/services'

const cardsStore = useCardsStore()
const servicesStore = useServicesStore()
const context = computed(() => servicesStore.context('Railway')?.data)
// Context.vue's choice of Railway's own views (a context with infra, not standalone), or a card of
// the simulator (with scenario_id): an event can end before the page has read the run's first
// context, polled every 5 s (F-36: scenario 2's door fault ends at step 9)
const simulatorRun = computed(
  () =>
    !standalone.value &&
    (!!context.value?.infra ||
      cardsStore
        .cards('Railway')
        .some((card) => (card.data.metadata as { scenario_id?: string })?.scenario_id))
)
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
