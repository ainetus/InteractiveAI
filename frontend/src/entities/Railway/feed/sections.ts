// The Railway feed's one section, with Railway's filter: only the running scenario's cards
// (see `currentRun.ts`). Passed to the shared feed through its `sections` option, so the shared
// component stays as it is.

import { isCardOfCurrentRun } from '@/entities/Railway/feed/currentRun'
import { useServicesStore } from '@/stores/services'
import type { Card } from '@/types/cards'
import type { Metadata } from '@/types/entities'

export const sections = [
  {
    name: 'main',
    weight: 1,
    filter: (card: Card) =>
      isCardOfCurrentRun(
        card.data.metadata as Partial<Metadata<'Railway'>>,
        useServicesStore().context('Railway')?.data
      )
  }
]
