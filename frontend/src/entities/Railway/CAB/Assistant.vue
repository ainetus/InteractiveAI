<template>
  <section class="cab-panel">
    <ModeChoice v-if="!mode" @choose="onModeChoice" />
    <Default>
      <template #title>
        <template v-if="appStore.tab.assistant === 2 && open">
          {{ $t('railway.journey.title') }}
        </template>
      </template>
      <Event
        v-if="appStore.tab.assistant === 1 && appStore.card('Railway')"
        :card="appStore.card('Railway')!"
        :primary-action="startJourney">
        <template #event>
          <i18n-t
            scope="global"
            :keypath="
              appStore.card('Railway')!.data.metadata.event_type === 'PASSENGER'
                ? 'event.text.passenger'
                : appStore.card('Railway')?.data.metadata.event_type === 'INFRASTRUCTURE' &&
                    !cardsStore
                      .cards('Railway')
                      .find(
                        (card) =>
                          card.data.parent_event_id === appStore.card('Railway')?.processInstanceId
                      )
                  ? 'event.text.infrastructure_childless'
                  : 'event.text'
            ">
            <template #event>
              <strong
                :style="{
                  color: `var(--color-${criticalityToColor(appStore.card('Railway')!.data.criticality)}`
                }">
                {{ appStore.card('Railway')!.titleTranslated }}
              </strong>
            </template>
          </i18n-t>
        </template>
      </Event>

      <div
        v-if="appStore.tab.assistant === 2 && appStore.card('Railway') && open && mode"
        class="railway-journey">
        <!-- The session's mode -->
        <header class="railway-journey-header">
          <strong class="railway-journey-mode">{{ $t(`railway.journey.mode.${mode}`) }}</strong>
        </header>

        <!-- KPI choice: several, in order of importance, or one with a threshold -->
        <div v-if="mode !== 'basic'" class="railway-journey-box">
          <p class="railway-journey-label">
            {{ mode === 'kpi' ? $t('railway.journey.select_kpis') : $t('railway.journey.select_kpi') }}
          </p>
          <div class="railway-journey-kpis">
            <button
              v-for="option of KPIS"
              :key="option.id"
              type="button"
              class="railway-journey-chip"
              :class="{ selected: priorities.includes(option.id) }"
              :aria-pressed="priorities.includes(option.id)"
              @click="mode === 'kpi' ? toggleKpi(option.id) : selectKpi(option.id)">
              <span v-if="mode === 'kpi' && priorities.includes(option.id)" class="railway-journey-chip-rank">
                {{ priorities.indexOf(option.id) + 1 }}
              </span>
              {{ $t(`Railway.kpis.${option.id}`) }}
            </button>
          </div>
          <template v-if="mode === 'kpi' && priorities.length">
            <p class="railway-journey-label">{{ $t('railway.journey.priorities') }}</p>
            <ol class="railway-journey-priorities">
              <li v-for="(id, index) of priorities" :key="id">
                <span class="railway-journey-priority-rank">{{ index + 1 }}</span>
                <span class="railway-journey-priority-name">{{ $t(`Railway.kpis.${id}`) }}</span>
                <button
                  type="button"
                  :disabled="index === 0"
                  :title="$t('railway.journey.priority.up')"
                  :aria-label="$t('railway.journey.priority.up')"
                  @click="moveKpi(index, -1)">
                  <ChevronUp :size="14" />
                </button>
                <button
                  type="button"
                  :disabled="index === priorities.length - 1"
                  :title="$t('railway.journey.priority.down')"
                  :aria-label="$t('railway.journey.priority.down')"
                  @click="moveKpi(index, 1)">
                  <ChevronDown :size="14" />
                </button>
                <button
                  type="button"
                  :title="$t('railway.journey.priority.remove')"
                  :aria-label="$t('railway.journey.priority.remove')"
                  @click="toggleKpi(id)">
                  <X :size="14" />
                </button>
              </li>
            </ol>
            <p v-if="priorities.length > 1" class="railway-journey-hint">
              {{ $t('railway.journey.priorities_hint') }}
            </p>
          </template>
          <!-- Every recommendation has the same value: there is nothing to set a threshold on -->
          <p
            v-if="mode === 'kpi-threshold' && kpi && range && range.min === range.max"
            class="railway-journey-hint railway-journey-same">
            <Info :size="14" />
            {{
              $t('railway.journey.threshold_same', {
                kpi: $t(`Railway.kpis.${kpi}`),
                value: formatThreshold(kpi, range.max)
              })
            }}
          </p>
          <template v-else-if="mode === 'kpi-threshold' && kpi && range">
            <div class="railway-journey-threshold">
              <div class="railway-journey-threshold-value">
                <label for="railway-threshold">
                  {{ $t('railway.journey.threshold') }}
                </label>
                <strong>≤ {{ formatThreshold(kpi, thresholdDraft) }}</strong>
              </div>
              <input
                id="railway-threshold"
                v-model.number="thresholdDraft"
                type="range"
                :min="range.min"
                :max="range.max"
                step="1"
                @change="commitThreshold" />
            </div>
            <p class="railway-journey-hint">
              {{ $t('railway.journey.threshold_hint', { kpi: $t(`Railway.kpis.${kpi}`) }) }}
            </p>
          </template>
        </div>

        <div v-if="mode !== 'basic' && !kpi" class="railway-journey-empty">
          <Target :size="28" />
          <p>{{ $t('railway.journey.select_kpi_hint') }}</p>
        </div>
        <div v-else-if="loading" class="railway-journey-empty">
          <p>{{ $t('railway.journey.loading') }}</p>
        </div>
        <template v-else>
          <!-- Recommendations -->
          <ol class="railway-journey-list">
            <li
              v-for="(recommendation, index) of visible"
              :key="recommendation.title"
              :class="{ selected: selected?.title === recommendation.title }"
              @click="select(recommendation)">
              <span class="railway-journey-rank" :style="{ '--rank': index }">{{ index + 1 }}</span>
              <span class="railway-journey-reco">
                <span>{{ recommendation.title }}</span>
                <span v-if="mode === 'basic' && isBest(recommendation)" class="railway-journey-expert">
                  <Star :size="10" /> {{ $t('railway.journey.expert_choice') }}
                </span>
              </span>
              <button
                type="button"
                class="railway-journey-reject"
                :title="$t('railway.journey.reject')"
                :aria-label="$t('railway.journey.reject')"
                @click.stop="reject(recommendation)">
                <ThumbsDown :size="14" />
              </button>
            </li>
          </ol>
          <p v-if="!recommendations.length && mode !== 'kpi-threshold'" class="railway-journey-hint">
            {{ $t('railway.journey.empty') }}
          </p>
          <p v-else-if="recommendations.length && !visible.length" class="railway-journey-hint">
            {{ $t('railway.journey.all_rejected') }}
          </p>
          <button
            v-if="rejected.length"
            type="button"
            class="railway-journey-restore"
            @click="restoreRejected">
            <RotateCcw :size="14" />
            {{ $t('railway.journey.restore', { count: rejected.length }, rejected.length) }}
          </button>

          <!-- Details of the selected recommendation -->
          <template v-if="selected">
            <div class="railway-journey-box">
              <p class="railway-journey-label"><FileText :size="14" /> {{ $t('railway.journey.description') }}</p>
              <p>{{ selected.description }}</p>
            </div>
            <template v-if="mode !== 'basic' && kpi">
              <div class="railway-journey-box">
                <p class="railway-journey-label"><Gauge :size="14" /> {{ $t('railway.journey.kpis') }}</p>
                <div
                  v-for="option of KPIS"
                  :key="option.id"
                  class="railway-journey-metric"
                  :class="{ chosen: priorities.includes(option.id) }">
                  <span>
                    <template v-if="mode === 'kpi' && priorities.length > 1 && priorities.includes(option.id)">
                      {{ priorities.indexOf(option.id) + 1 }}.
                    </template>
                    {{ $t(`Railway.kpis.${option.id}`) }}
                  </span>
                  <span>{{ formatKpi(option.id, kpiValue(selected, option.id)) }}</span>
                </div>
              </div>
              <div class="railway-journey-box">
                <p class="railway-journey-label">
                  <Lightbulb :size="14" /> {{ $t('railway.journey.explainability') }}
                </p>
                <p>{{ explanation }}</p>
              </div>
            </template>
            <Button class="railway-journey-apply" @click="confirming = true">
              <Check :size="16" />
              {{ $t('railway.journey.apply') }}
            </Button>
          </template>
        </template>
      </div>
    </Default>

    <Modal v-if="confirming" type="choice" @close="onConfirm">
      <i18n-t scope="global" keypath="railway.journey.confirm">
        <template #recommendation>
          <strong style="color: var(--color-primary)">{{ selected?.title }}</strong>
        </template>
      </i18n-t>
    </Modal>
    <Modal v-if="noRecommendation" type="info" @close="resetThreshold">
      {{ $t('railway.journey.no_reco') }}
    </Modal>
  </section>
</template>
<script setup lang="ts">
import {
  Check,
  ChevronDown,
  ChevronUp,
  FileText,
  Gauge,
  Info,
  Lightbulb,
  RotateCcw,
  Star,
  Target,
  ThumbsDown,
  X
} from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { sendTrace } from '@/api/services'
import Button from '@/components/atoms/Button.vue'
import Modal from '@/components/atoms/Modal.vue'
import Default from '@/components/organisms/CAB/Assistant.vue'
import Event from '@/components/organisms/CAB/Assistant/Event.vue'
import { applyRecommendation } from '@/entities/Railway/api'
import ModeChoice from '@/entities/Railway/CAB/ModeChoice.vue'
import { currentLanguage } from '@/plugins/i18n'
import { useAppStore } from '@/stores/app'
import { useCardsStore } from '@/stores/cards'
import { useServicesStore } from '@/stores/services'
import type { Recommendation } from '@/types/services'
import {
  type RailwayMode as Mode,
  recordTraceForSession,
  sessionRailwayMode,
  setSessionRailwayMode
} from '@/utils/traceSessionExport'
import { criticalityToColor, getRootCard } from '@/utils/utils'

/**
 * Human experiment: at the start of the session the operator picks how the
 * recommendations are presented - the experts' ranking, sorted on a KPI, or
 * sorted on a KPI under a threshold. The mode holds for the whole session
 * (reloads included, cleared on logout) and is traced and exported with it.
 */
type Kpi = 'cost' | 'delay' | 'nb_impacted_passengers' | 'total_cost'

/** The recommendation service's ordering for each mode (see resources/Railway/manager.py) */
const SERVICE_MODE: Record<Mode, string> = {
  basic: 'basic', // the experts' choice first
  kpi: 'risk', // sorted on the chosen KPIs, in their order of importance
  'kpi-threshold': 'deontic' // above the threshold left out, then sorted by the KPI
}
/** The service's name for each KPI of the recommendations */
const KPIS: { id: Kpi; sortType: string }[] = [
  { id: 'cost', sortType: 'cost' },
  { id: 'delay', sortType: 'delay' },
  { id: 'nb_impacted_passengers', sortType: 'passengers' },
  { id: 'total_cost', sortType: 'total_cost' }
]

const { t, locale } = useI18n()
const cardsStore = useCardsStore()
const servicesStore = useServicesStore()
const appStore = useAppStore()

const mode = ref<Mode | undefined>(sessionRailwayMode())
/** Whether the recommendations of the selected event are open */
const open = ref(false)

function onModeChoice(choice: Mode) {
  setSessionRailwayMode(choice)
  mode.value = choice
}

/** Every recommendation of the event, to bound the threshold to the values it can take */
const all = ref<Recommendation<'Railway'>[]>([])
const recommendations = ref<Recommendation<'Railway'>[]>([])
const rejected = ref<string[]>([])
const visible = computed(() =>
  recommendations.value.filter((recommendation) => !rejected.value.includes(recommendation.title))
)
const selected = ref<Recommendation<'Railway'>>()
/**
 * The chosen KPIs, most important first: several in the KPI mode (sorted on
 * the first, ties broken by the next ones, no weights), one with a threshold
 */
const priorities = ref<Kpi[]>([])
const kpi = computed<Kpi | undefined>(() => priorities.value[0])
/** The threshold sent to the service, and the slider's value while it moves */
const threshold = ref<number>()
const thresholdDraft = ref(0)
const loading = ref(false)
const confirming = ref(false)
const noRecommendation = ref(false)
const askedAt = ref<string>()
const shownAt = ref<string>()
/** Answers to an older request (a KPI changed in between) are dropped */
let request = 0

const range = computed(() => {
  if (!kpi.value || !all.value.length) return
  const values = all.value.map((recommendation) => kpiValue(recommendation, kpi.value!))
  return { min: Math.min(...values), max: Math.max(...values) }
})

watch(
  () => appStore._card,
  () => {
    open.value = false
    appStore.tab.assistant = 1
  }
)

/** A KPI as a number: minutes for a delay ("1h30", "00h53", "45min"), the value otherwise */
function kpiValue(recommendation: Recommendation<'Railway'>, key: Kpi) {
  const raw = recommendation.kpis?.[key]
  if (key !== 'delay') return Number(raw) || 0
  const text = String(raw ?? '').toLowerCase()
  const hours = /(\d+)\s*h/.exec(text)
  const minutes = /h\s*(\d+)/.exec(text) ?? /(\d+)\s*min/.exec(text)
  if (!hours && !minutes) return Number(text) || 0
  return Number(hours?.[1] ?? 0) * 60 + Number(minutes?.[1] ?? 0)
}

function formatKpi(key: Kpi, value: number) {
  if (key === 'delay') return `${Math.floor(value / 60)}h${String(value % 60).padStart(2, '0')}`
  return value.toLocaleString(locale.value)
}

/** A threshold with its unit: euros for the costs, passengers for the impacted passengers */
function formatThreshold(key: Kpi, value: number) {
  if (key === 'cost' || key === 'total_cost')
    return value.toLocaleString(locale.value, {
      style: 'currency',
      currency: 'EUR',
      maximumFractionDigits: 0
    })
  if (key === 'nb_impacted_passengers')
    return t('railway.journey.unit.passengers', { count: value.toLocaleString(locale.value) }, value)
  return formatKpi(key, value)
}

function isBest(recommendation: Recommendation<'Railway'>) {
  return String(recommendation.kpis?.best).toLowerCase() === 'true'
}

const explanation = computed(() => {
  if (!selected.value || !kpi.value) return ''
  if (priorities.value.length > 1)
    return t('railway.journey.explain.priorities', {
      rank: visible.value.findIndex((recommendation) => recommendation.title === selected.value!.title) + 1,
      count: visible.value.length,
      kpis: priorities.value.map((id) => t(`Railway.kpis.${id}`)).join(' > ')
    })
  const values = visible.value.map((recommendation) => kpiValue(recommendation, kpi.value!))
  const value = kpiValue(selected.value, kpi.value)
  let text = t('railway.journey.explain.rank', {
    rank: visible.value.findIndex((recommendation) => recommendation.title === selected.value!.title) + 1,
    count: visible.value.length,
    kpi: t(`Railway.kpis.${kpi.value}`),
    value: formatKpi(kpi.value, value),
    best: formatKpi(kpi.value, Math.min(...values))
  })
  if (mode.value === 'kpi-threshold' && threshold.value !== undefined)
    text +=
      ' ' +
      t('railway.journey.explain.threshold', {
        value: formatKpi(kpi.value, value),
        threshold: formatKpi(kpi.value, threshold.value)
      })
  return text
})

/** What the analysis needs to know about how the recommendations were presented */
function experimentRecord() {
  return {
    mode: mode.value!,
    kpi: kpi.value ?? null,
    kpis: [...priorities.value],
    threshold: threshold.value ?? null
  }
}

async function startJourney() {
  if (!mode.value) return
  const card = appStore.card('Railway')!
  priorities.value = []
  threshold.value = undefined
  rejected.value = []
  selected.value = undefined
  recommendations.value = []
  open.value = true
  appStore.tab.assistant = 2
  loading.value = true
  const answer = await servicesStore.getRecommendation(card, undefined, undefined, {
    mode: 'basic',
    lang: currentLanguage()
  })
  // No context yet: the store has told the operator and closed the assistant
  if (!answer) {
    open.value = false
    loading.value = false
    return
  }
  all.value = answer
  loading.value = false
  askedAt.value = new Date().toISOString()
  sendTrace({
    data: { id: appStore.card('Railway')!.id, railway_experiment: experimentRecord() },
    use_case: 'Railway',
    step: 'ASKFORHELP'
  })
  if (mode.value === 'basic') fetchRecommendations()
}

async function fetchRecommendations() {
  if (!mode.value || (mode.value !== 'basic' && !kpi.value)) return
  const id = ++request
  loading.value = true
  // Titles and descriptions come in the language being displayed
  const overrides: Record<string, unknown> = { mode: SERVICE_MODE[mode.value], lang: currentLanguage() }
  // The chosen KPIs, most important first: the agent sorts on the first, ties broken by the next ones
  const sortTypes = priorities.value.map((id) => KPIS.find((option) => option.id === id)!.sortType)
  if (sortTypes.length) overrides.sort_type = sortTypes[0]
  if (mode.value === 'kpi') overrides.sort_types = sortTypes
  if (mode.value === 'kpi-threshold') overrides.threshold_value = threshold.value
  try {
    const answer = await servicesStore.getRecommendation(
      appStore.card('Railway')!,
      undefined,
      undefined,
      overrides
    )
    if (id !== request) return
    recommendations.value = answer ?? []
  } finally {
    if (id === request) loading.value = false
  }
  if (selected.value && !visible.value.some((recommendation) => recommendation.title === selected.value!.title))
    selected.value = undefined
  if (!recommendations.value.length) {
    if (mode.value === 'kpi-threshold') noRecommendation.value = true
    return
  }
  shownAt.value = new Date().toISOString()
  recordTraceForSession({
    use_case: 'Railway',
    step: 'RECOMMENDATIONS',
    date: shownAt.value,
    data: {
      recommendations: recommendations.value.map((recommendation) => recommendation.title),
      railway_experiment: experimentRecord()
    }
  })
}

/** KPI mode: adds a KPI as the least important one, or takes it out */
function toggleKpi(id: Kpi) {
  if (priorities.value.includes(id)) priorities.value = priorities.value.filter((item) => item !== id)
  else priorities.value = [...priorities.value, id]
  if (priorities.value.length) fetchRecommendations()
  else {
    // Nothing to sort on any more: back to asking for a KPI
    ++request
    loading.value = false
    recommendations.value = []
    selected.value = undefined
  }
}

/** KPI mode: moves a KPI one place up (-1) or down (1) in the order of importance */
function moveKpi(index: number, direction: -1 | 1) {
  const target = index + direction
  if (target < 0 || target >= priorities.value.length) return
  const order = [...priorities.value]
  ;[order[index], order[target]] = [order[target], order[index]]
  priorities.value = order
  fetchRecommendations()
}

/** Threshold mode: the one KPI the threshold applies to */
function selectKpi(id: Kpi) {
  if (kpi.value === id) return
  priorities.value = [id]
  if (mode.value === 'kpi-threshold') {
    // Starts with every recommendation allowed; lowering it is the operator's choice
    threshold.value = range.value?.max
    thresholdDraft.value = range.value?.max ?? 0
  }
  fetchRecommendations()
}

function commitThreshold() {
  threshold.value = thresholdDraft.value
  fetchRecommendations()
}

function resetThreshold() {
  noRecommendation.value = false
  thresholdDraft.value = range.value?.max ?? 0
  commitThreshold()
}

function select(recommendation: Recommendation<'Railway'>) {
  selected.value = selected.value?.title === recommendation.title ? undefined : recommendation
}

function reject(recommendation: Recommendation<'Railway'>) {
  rejected.value.push(recommendation.title)
  if (selected.value?.title === recommendation.title) selected.value = undefined
  recordTraceForSession({
    use_case: 'Railway',
    step: 'FEEDBACK',
    date: new Date().toISOString(),
    data: {
      action: 'reject_recommendation',
      recommendation: recommendation.title,
      railway_experiment: experimentRecord()
    }
  })
}

/** Brings back every recommendation rejected for this event */
function restoreRejected() {
  recordTraceForSession({
    use_case: 'Railway',
    step: 'FEEDBACK',
    date: new Date().toISOString(),
    data: {
      action: 'restore_rejected_recommendations',
      recommendations: [...rejected.value],
      railway_experiment: experimentRecord()
    }
  })
  rejected.value = []
}

async function onConfirm(success: boolean) {
  confirming.value = false
  if (!success || !selected.value || !open.value) return
  const card = appStore.card('Railway')!
  const recommendation = selected.value
  const record = {
    ...experimentRecord(),
    shown: visible.value.map((item) => item.title),
    rejected: [...rejected.value],
    chosen_rank: visible.value.findIndex((item) => item.title === recommendation.title) + 1,
    asked_at: askedAt.value,
    shown_at: shownAt.value
  }
  sendTrace({
    data: { ...recommendation, railway_experiment: record },
    use_case: 'Railway',
    step: 'AWARD'
  })
  try {
    await applyRecommendation({
      ...recommendation.actions[0],
      event_id: getRootCard(card).processInstanceId,
      recommendation: recommendation.title,
      experiment: {
        mode: record.mode,
        kpi: record.kpi,
        kpis: record.kpis,
        threshold: record.threshold
      }
    })
  } catch {
    // http plugin already shows an error modal — stay here so the operator can retry
    return
  }
  cardsStore.resolveCriticality(card)
  open.value = false
  appStore.tab.assistant = 0
}
</script>
<style lang="scss">
.railway-journey {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
  overflow-y: auto;
  font-size: 0.9em;

  &-mode {
    color: var(--color-primary);
  }

  &-box {
    display: flex;
    flex-direction: column;
    gap: calc(var(--unit) * 0.5);
    padding: var(--spacing-1);
    border: 1px solid var(--color-grey-300);
    border-radius: var(--radius-medium);
  }
  &-label {
    display: flex;
    align-items: center;
    gap: calc(var(--unit) * 0.5);
    font-weight: bold;
  }
  &-hint {
    color: var(--color-grey-600);
    font-size: 0.9em;
  }

  &-kpis {
    display: flex;
    flex-wrap: wrap;
    gap: calc(var(--unit) * 0.5);
  }
  &-chip {
    cursor: pointer;
    padding: calc(var(--unit) * 0.5) var(--spacing-1);
    border: 1px solid var(--color-grey-400);
    border-radius: var(--radius-circular);
    background: var(--color-background);
    color: var(--color-text);
    &:hover {
      border-color: var(--color-primary);
    }
    &.selected {
      background: var(--color-primary);
      border-color: var(--color-primary);
      color: var(--color-text-inverted);
    }
    &-rank {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 1.4em;
      height: 1.4em;
      margin-right: calc(var(--unit) * 0.25);
      border-radius: var(--radius-circular);
      background: var(--color-text-inverted);
      color: var(--color-primary);
      font-size: 0.85em;
      font-weight: bold;
    }
  }
  &-priorities {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: calc(var(--unit) * 0.5);
    li {
      display: flex;
      align-items: center;
      gap: calc(var(--unit) * 0.5);
      padding: calc(var(--unit) * 0.25) calc(var(--unit) * 0.5);
      border: 1px solid var(--color-grey-300);
      border-radius: var(--radius-medium);
    }
    button {
      cursor: pointer;
      flex: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: calc(var(--unit) * 3);
      height: calc(var(--unit) * 3);
      border: 1px solid var(--color-grey-300);
      border-radius: var(--radius-small, 4px);
      background: var(--color-background);
      color: var(--color-text);
      &:hover:not(:disabled) {
        border-color: var(--color-primary);
        color: var(--color-primary);
      }
      &:disabled {
        cursor: default;
        opacity: 0.35;
      }
    }
  }
  &-priority-rank {
    flex: none;
    width: 1.6em;
    font-weight: bold;
    color: var(--color-primary);
    text-align: center;
  }
  &-priority-name {
    flex: 1;
    min-width: 0;
  }
  // Value above the slider, so a long one ("12 345 voyageurs") never squeezes it
  &-threshold {
    display: flex;
    flex-direction: column;
    gap: calc(var(--unit) * 0.5);
    input {
      width: 100%;
      margin: 0;
      accent-color: var(--color-primary);
    }
    &-value {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      justify-content: space-between;
      gap: calc(var(--unit) * 0.5);
      strong {
        color: var(--color-primary);
        text-align: right;
      }
    }
  }

  &-same {
    display: flex;
    align-items: flex-start;
    gap: calc(var(--unit) * 0.5);
    .lucide {
      flex: none;
      margin-top: 0.2em;
    }
  }

  &-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-1);
    padding: var(--spacing-2);
    color: var(--color-grey-600);
    text-align: center;
  }

  &-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: calc(var(--unit) * 0.5);
    li {
      display: flex;
      align-items: stretch;
      cursor: pointer;
      min-height: calc(var(--unit) * 5);
      border: 1px solid var(--color-grey-300);
      border-radius: var(--radius-medium);
      overflow: hidden;
      &:hover {
        border-color: var(--color-primary);
      }
      &.selected {
        border: 2px solid var(--color-primary);
        background: color-mix(in srgb, var(--color-primary), transparent 92%);
      }
    }
  }
  &-rank {
    display: flex;
    align-items: center;
    justify-content: center;
    flex: none;
    width: calc(var(--unit) * 3.5);
    font-weight: bold;
    color: var(--color-text-inverted);
    background: color-mix(in srgb, var(--color-primary), transparent calc(var(--rank) * 22%));
  }
  &-reco {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: calc(var(--unit) * 0.25);
    padding: calc(var(--unit) * 0.5) var(--spacing-1);
    font-weight: bold;
  }
  &-expert {
    align-self: flex-start;
    display: inline-flex;
    align-items: center;
    gap: calc(var(--unit) * 0.25);
    padding: 0 var(--spacing-1);
    font-size: 0.8em;
    border-radius: var(--radius-circular);
    color: var(--color-warning);
    border: 1px solid var(--color-warning);
  }
  &-reject {
    cursor: pointer;
    flex: none;
    width: calc(var(--unit) * 4);
    border: none;
    background: var(--color-primary);
    color: var(--color-text-inverted);
    &:hover {
      background: var(--color-error);
    }
  }
  &-restore {
    cursor: pointer;
    align-self: flex-start;
    display: inline-flex;
    align-items: center;
    gap: calc(var(--unit) * 0.5);
    padding: calc(var(--unit) * 0.5) var(--spacing-1);
    border: 1px solid var(--color-primary);
    border-radius: var(--radius-circular);
    background: var(--color-background);
    color: var(--color-primary);
    &:hover {
      background: color-mix(in srgb, var(--color-primary), transparent 90%);
    }
  }

  &-metric {
    display: flex;
    justify-content: space-between;
    padding: calc(var(--unit) * 0.25) 0;
    border-bottom: 1px solid var(--color-grey-200);
    &:last-child {
      border-bottom: none;
    }
    &.chosen {
      font-weight: bold;
      color: var(--color-primary);
    }
  }

  &-apply {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: calc(var(--unit) * 0.5);
    width: 100%;
  }
}
</style>
