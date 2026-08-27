<template>
  <section class="cab-panel">
    <div style="padding: 16px; height: 100%; overflow-y: auto; overflow-x: hidden;">

      <!-- IDLE — no scenario running -->
      <div v-if="state === 'idle'" class="scenario-idle">
        <div class="scenario-title">Fahrtdisponent-Training</div>
        <div class="scenario-subtitle">
          Klicke auf <strong>Sitzung laden</strong> im Szenario-Panel, um ein Szenario zu starten.
        </div>
      </div>

      <!-- RUNNING — simulation in progress, waiting for decision point -->
      <div v-if="state === 'running'" class="scenario-running">
        <div class="scenario-badge">▶ Running</div>
        <div class="scenario-title">{{ scenarioName }}</div>
        <div class="scenario-subtitle">Zugbewegungen werden überwacht... Schritt {{ step }}</div>
        <div style="margin-top: 16px; font-size: 12px; opacity: 0.6;">
          Eine Entscheidung wird erforderlich, sobald ein Konflikt erkannt wird.
        </div>
      </div>

      <!-- PAUSED — Ko-Lernen Modus -->
      <div v-if="state === 'paused_for_decision' && mode === 'colearning'" class="scenario-decision">
        <div class="scenario-badge alarm">⚠ Entscheidung erforderlich</div>
        <div class="scenario-title">{{ scenarioName }}</div>
        <div class="decision-description">{{ activeDecision?.description }}</div>

        <div class="kl-section-label">Zug auswählen:</div>
        <div class="kl-train-list">
          <button
            v-for="t in conflictTrains"
            :key="t"
            class="kl-train-btn"
            :class="{ 'kl-train-btn-active': klTrain === t }"
            @click="selectTrain(t)"
          >🚆 {{ trainNames[t] || t }}</button>
          <span v-if="conflictTrains.length === 0" style="font-size:12px;opacity:0.5;">
            Keine betroffenen Züge gefunden.
          </span>
        </div>

        <div class="kl-section-label">Aktion auswählen:</div>
        <div class="kl-actions">
          <button
            class="kl-btn"
            :class="{ 'kl-btn-active': klAction === 'warten' }"
            :disabled="!!klTrain && !trainActions[klTrain]?.includes('warten')"
            @click="klAction = 'warten'"
          >⏸ Warten</button>
          <button
            v-if="!klTrain || trainActions[klTrain]?.includes('vorfahrt')"
            class="kl-btn"
            :class="{ 'kl-btn-active': klAction === 'vorfahrt' }"
            :disabled="!!klTrain && !trainActions[klTrain]?.includes('vorfahrt')"
            @click="klAction = 'vorfahrt'"
          >🚦 Vorfahrt</button>
          <button
            v-if="!klTrain || trainActions[klTrain]?.includes('umleiten')"
            class="kl-btn"
            :class="{ 'kl-btn-active': klAction === 'umleiten' }"
            :disabled="!!klTrain && !trainActions[klTrain]?.includes('umleiten')"
            @click="klAction = 'umleiten'"
          >🔀 Umleiten</button>
        </div>

        <div v-if="klError" class="kl-error">{{ klError }}</div>
        <div v-if="klApplied" class="kl-success">✓ Lösung angewendet.</div>

        <button
          class="btn-primary"
          :disabled="!klTrain || !klAction"
          @click="applyColearning"
          style="margin-top: 14px;"
        >Lösung vorschlagen</button>

        <!-- Invalid action toast -->
        <div v-if="colearningError" class="kl-error-toast">
          ⚠ {{ colearningError }}
        </div>
      </div>

      <!-- PAUSED — Empfehlungsmodus -->
      <div v-if="state === 'paused_for_decision' && mode !== 'colearning'" class="scenario-decision">
        <div class="scenario-badge alarm">⚠ Entscheidung erforderlich</div>
        <div class="scenario-title">{{ scenarioName }}</div>
        <div class="decision-description">{{ activeDecision?.description }}</div>

        <!-- KPI table — all options side by side -->
        <div class="kpi-table-wrapper" v-if="activeDecision">
          <table class="kpi-table">
            <thead>
              <tr>
                <th>KPI</th>
                <th
                  v-for="(opt, i) in activeDecision.options"
                  :key="i"
                  :class="{ selected: selectedOption === i }"
                >
                  Option {{ String.fromCharCode(65 + i) }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="kpi-label">Lok. Verspätung</td>
                <td
                  v-for="(opt, i) in activeDecision.options"
                  :key="i"
                  :class="{ selected: selectedOption === i }"
                >
                  <span :class="delayClass(opt.kpis.local_delay)">
                    {{ opt.kpis.local_delay }} min
                  </span>
                </td>
              </tr>
              <tr>
                <td class="kpi-label">Glob. Verspätung</td>
                <td
                  v-for="(opt, i) in activeDecision.options"
                  :key="i"
                  :class="{ selected: selectedOption === i }"
                >
                  <span :class="delayClass(opt.kpis.global_delay)">
                    {{ opt.kpis.global_delay }} min
                  </span>
                </td>
              </tr>
              <tr>
                <td class="kpi-label">Energieeffizienz</td>
                <td
                  v-for="(opt, i) in activeDecision.options"
                  :key="i"
                  :class="{ selected: selectedOption === i }"
                >
                  <span :class="scoreClass(opt.kpis.energy)">
                    {{ opt.kpis.energy }} %
                  </span>
                </td>
              </tr>
              <tr>
                <td class="kpi-label">Anschlüsse</td>
                <td
                  v-for="(opt, i) in activeDecision.options"
                  :key="i"
                  :class="{ selected: selectedOption === i }"
                >
                  <span :class="connectionClass(opt.kpis.anschluss)">
                    {{ opt.kpis.anschluss }} gefährdet
                  </span>
                </td>
              </tr>
              <tr class="option-row">
                <td class="kpi-label">Aktion</td>
                <td
                  v-for="(opt, i) in activeDecision.options"
                  :key="i"
                >
                  <button
                    class="btn-option"
                    :class="{ 'btn-option-selected': selectedOption === i }"
                    @click="selectOption(i)"
                  >
                    {{ opt.label }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Confirm button -->
        <div style="margin-top: 16px; text-align: center;">
          <button
            class="btn-primary"
            :disabled="selectedOption === null"
            @click="showConfirmModal = true"
          >
            Lösung vorschlagen
          </button>
        </div>

        <!-- Confirmation popup -->
        <div v-if="showConfirmModal" class="confirm-overlay">
          <div class="confirm-modal">
            <div class="confirm-title">Lösung bestätigen</div>
            <div class="confirm-body">
              Möchtest du diese Lösung wirklich anwenden?
            </div>
            <div class="confirm-actions">
              <button class="btn-secondary" @click="showConfirmModal = false">Abbrechen</button>
              <button class="btn-primary" @click="confirmDecision">Bestätigen</button>
            </div>
          </div>
        </div>
      </div>

      <!-- COMPLETE — scenario done -->
      <div v-if="state === 'complete'" class="scenario-complete">
        <div class="scenario-badge success">✓ Szenario abgeschlossen</div>
        <div class="scenario-title">{{ scenarioName }}</div>
        <div class="scenario-subtitle">
          Alle Entscheidungen gespeichert. Nächstes Szenario wird geladen...
        </div>
        <button class="btn-primary" @click="nextScenario">Next Scenario</button>
      </div>

      <!-- SESSION COMPLETE -->
      <div v-if="state === 'session_complete'" class="scenario-complete">
        <div class="scenario-badge success">✓ Session Complete</div>
        <div class="scenario-title">Vielen Dank!</div>
        <div class="scenario-subtitle">Alle Szenarien abgeschlossen. Ihre Entscheidungen wurden gespeichert.</div>
        <div v-if="decisions.length > 0" style="margin-top: 16px;">
          <div style="font-weight: bold; margin-bottom: 8px; font-size: 13px;">Deine Entscheidungen:</div>
          <div
            v-for="(d, i) in decisions"
            :key="i"
            style="background: rgba(255,255,255,0.05); border-radius: 6px; padding: 8px; margin-bottom: 6px; font-size: 12px;"
          >
            <strong>{{ d.scenario_id }}</strong> — Decision {{ d.decision_index + 1 }}:
            {{ d.option_label }}
          </div>
        </div>
      </div>

    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { sendTrace } from '@/api/services'

const BRAIN_URL  = import.meta.env.VITE_RAILWAY_SIMU || 'http://localhost:5001'

const state          = ref<string>('idle')
const scenarioName   = ref<string>('')
const step           = ref<number>(0)
const activeDecision = ref<any>(null)
const selectedOption = ref<number | null>(null)
const sessionId      = ref<string>('')
const decisions      = ref<any[]>([])
const decisionError  = ref<string>('')
const applied        = ref<boolean>(false)
const showConfirmModal   = ref<boolean>(false)
const trainNames         = ref<Record<string,string>>({})
const colearningError    = ref<string>('')
// CoLearning mode state
const mode           = ref<string>('recommendation')
const conflictTrains = ref<string[]>([])
const trainActions   = ref<Record<string, string[]>>({})
const klTrain        = ref<string>('')
const klAction       = ref<string>('')
const klError        = ref<string>('')
const klApplied      = ref<boolean>(false)

let pollInterval: ReturnType<typeof setInterval> | null = null

// -- Session management ────────────────────────────────────────────────────────

async function startSession() {
  try {
    const res  = await fetch(`${BRAIN_URL}/session/start`, { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: '{}' })
    const data = await res.json()
    sessionId.value    = data.session_id
    scenarioName.value = data.scenario_name
    state.value        = 'running'
    startPolling()
  } catch (e) {
    console.error('Failed to start session:', e)
  }
}

async function nextScenario() {
  try {
    const res  = await fetch(`${BRAIN_URL}/session/next`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ session_id: sessionId.value }),
    })
    const data = await res.json()
    if (data.status === 'session_complete') {
      decisions.value = data.decisions
      state.value     = 'session_complete'
      stopPolling()
    } else {
      scenarioName.value   = data.scenario_name
      state.value          = 'running'
      selectedOption.value = null
      activeDecision.value = null
      startPolling()  // restart polling for next scenario
    }
  } catch (e) {
    console.error('Failed to advance scenario:', e)
  }
}

// -- Decision handling ─────────────────────────────────────────────────────────

function selectOption(index: number) {
  selectedOption.value = index
}

async function confirmDecision() {
  if (selectedOption.value === null) return
  showConfirmModal.value = false
  decisionError.value    = ''

  // Log AWARD trace to InteractiveAI history service
  const cardId = 'cabProcess.scenario_event_30'
  try {
    sendTrace({
      data:     { id: cardId, option_index: selectedOption.value } as any,
      use_case: 'Railway',
      step:     'AWARD',
    })
  } catch {}

  try {
    const res  = await fetch(`${BRAIN_URL}/session/decision`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        session_id:   sessionId.value,
        option_index: selectedOption.value,
      }),
    })
    const data = await res.json()
    if (data.error) {
      decisionError.value = data.error
      console.error('Decision error:', data.error)
    } else {
      console.log('Decision applied:', data)
      applied.value        = true
      selectedOption.value = null
      state.value          = 'running'
      setTimeout(() => { applied.value = false }, 3000)
    }
  } catch (e) {
    decisionError.value = 'Netzwerkfehler — Flask-Server nicht erreichbar.'
    console.error('Failed to apply decision:', e)
  }
}

// -- Status polling ────────────────────────────────────────────────────────────

async function selectTrain(train: string) {
  klTrain.value  = train
  klAction.value = ''  // reset action when train changes
  // Notify Flask so map can highlight the selected train
  try {
    await fetch(`${BRAIN_URL}/session/selected_train`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ train }),
    })
  } catch {}
}

async function applyColearning() {
  if (!klTrain.value || !klAction.value) return
  klError.value   = ''
  klApplied.value = false
  try {
    const res  = await fetch(`${BRAIN_URL}/session/colearning_action`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        session_id: sessionId.value,
        train:      klTrain.value,
        action:     klAction.value,
      }),
    })
    const data = await res.json()
    if (!data.feasible) {
      colearningError.value = data.message || '⚠ Ungültige Aktion für dieses Szenario.'
      setTimeout(() => { colearningError.value = '' }, 3000)
    } else {
      klApplied.value = true
      klTrain.value   = ''
      klAction.value  = ''
      state.value     = 'running'
      // Clear map highlight
      try { await fetch(`${BRAIN_URL}/session/selected_train`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{"train":""}' }) } catch {}
    }
  } catch {
    klError.value = 'Verbindungsfehler zum Flask-Server.'
  }
}

function startPolling() {
  pollInterval = setInterval(pollStatus, 2000)
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

async function pollStatus() {
  try {
    const res  = await fetch(`${BRAIN_URL}/session/status`)
    const data = await res.json()

    step.value = data.step ?? 0
    // Pick up session_id and mode from status
    if (data.session_id && !sessionId.value) {
      sessionId.value = data.session_id
    }
    if (data.mode) mode.value = data.mode
    if (data.conflict_trains) conflictTrains.value = data.conflict_trains
    if (data.train_actions)   trainActions.value   = data.train_actions

    if (data.state === 'paused_for_decision') {
      // Send ASKFORHELP trace only on first detection
      if (state.value !== 'paused_for_decision') {
        // Use the processInstanceId of our decision-point event card
        const cardId = 'cabProcess.scenario_event_30'
        try {
          sendTrace({
            data:     { id: cardId } as any,
            use_case: 'Railway',
            step:     'ASKFORHELP',
          })
        } catch {}
      }
      trainNames.value     = data.train_names || {}
      activeDecision.value = data.active_decision
      state.value          = 'paused_for_decision'
    } else if (data.state === 'complete') {
      state.value = 'complete'
      // Don't stop polling — new session may start
    } else if (data.state === 'running') {
      // Reset from complete/session_complete when new session detected
      if (state.value === 'complete' || state.value === 'session_complete') {
        selectedOption.value = null
        activeDecision.value = null
        decisions.value      = []
        klTrain.value        = ''
        klAction.value       = ''
        klApplied.value      = false
      }
      if (data.scenario_name) scenarioName.value = data.scenario_name
      state.value = 'running'
    } else if (data.state === 'idle' && state.value === 'idle') {
      // still idle — no change
    }
  } catch {
    // Fail silently
  }
}

// -- KPI colour coding ─────────────────────────────────────────────────────────

// Delay in minutes — lower is better
function delayClass(minutes: number): string {
  if (minutes <= 10) return 'score-good'
  if (minutes <= 25) return 'score-medium'
  return 'score-poor'
}

// Energy efficiency in % — higher is better
function scoreClass(score: number): string {
  if (score >= 80) return 'score-good'
  if (score >= 65) return 'score-medium'
  return 'score-poor'
}

// Endangered connections count — lower is better
function connectionClass(count: number): string {
  if (count <= 1) return 'score-good'
  if (count <= 3) return 'score-medium'
  return 'score-poor'
}

// -- Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(() => {
  pollStatus()           // immediate first check
  startPolling()         // then every 2 seconds
})
onUnmounted(() => { stopPolling() })
</script>

<style scoped>
.scenario-idle,
.scenario-running,
.scenario-decision,
.scenario-complete {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.scenario-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: bold;
  background: rgba(255,255,255,0.1);
  color: #ccc;
  width: fit-content;
}
.scenario-badge.alarm   { background: rgba(220,50,50,0.2);  color: #ff6b6b; }
.scenario-badge.success { background: rgba(50,200,50,0.2);  color: #6bff6b; }

.scenario-title    { font-weight: bold; font-size: 15px; }
.scenario-subtitle { font-size: 12px; opacity: 0.7; }
.decision-description {
  font-size: 13px;
  background: rgba(255,255,255,0.05);
  border-radius: 6px;
  padding: 10px;
  line-height: 1.5;
}

/* KPI table */
.kpi-table-wrapper { overflow-x: auto; margin-top: 12px; }
.kpi-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.kpi-table th {
  background: rgba(255,255,255,0.08);
  padding: 6px 10px;
  text-align: center;
  font-weight: bold;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.kpi-table td {
  padding: 6px 10px;
  text-align: center;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
.kpi-table .kpi-label {
  text-align: left;
  opacity: 0.8;
  font-weight: 500;
}
.kpi-table td.selected,
.kpi-table th.selected {
  background: rgba(100,160,255,0.1);
}
.option-row td { padding-top: 10px; }

.score-good   { color: #6bff6b; font-weight: bold; }
.score-medium { color: #ffd06b; font-weight: bold; }
.score-poor   { color: #ff6b6b; font-weight: bold; }

/* Buttons */
.btn-primary {
  padding: 8px 20px;
  background: #2d6abf;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: bold;
  width: fit-content;
}
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-primary:hover:not(:disabled) { background: #3a7fd4; }

.btn-option {
  padding: 6px 10px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.2);
  color: #ccc;
  border-radius: 6px;
  cursor: pointer;
  font-size: 11px;
  width: 100%;
  text-align: center;
  transition: all 0.15s;
}
.btn-option:hover { background: rgba(255,255,255,0.1); }
.btn-option-selected {
  background: rgba(100,160,255,0.2);
  border-color: #6aaeff;
  color: #6aaeff;
  font-weight: bold;
}

/* -- Ko-Lernen UI -- */
.kl-train-buttons {
  display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 4px;
}
.kl-train-btn {
  padding: 7px 14px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.2);
  color: #ccc; border-radius: 7px; cursor: pointer;
  font-size: 12px; font-weight: bold; transition: all 0.15s;
}
.kl-train-btn:hover { background: rgba(255,255,255,0.12); }
.kl-train-btn-active {
  background: rgba(255,200,50,0.15);
  border-color: #ffc832;
  color: #ffc832;
}
.kl-section-label {
  font-size: 11px; font-weight: bold; opacity: 0.7;
  margin-top: 12px; margin-bottom: 5px; letter-spacing: 0.5px;
}
.kl-train-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 2px;
}
.kl-train-btn {
  padding: 7px 14px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.2);
  color: #ccc;
  border-radius: 7px;
  cursor: pointer;
  font-size: 13px;
  font-weight: bold;
  transition: all 0.15s;
}
.kl-train-btn:hover { background: rgba(255,255,255,0.1); }
.kl-train-btn-active {
  background: rgba(255,200,50,0.18);
  border-color: #ffc832;
  color: #ffc832;
}
.kl-actions { display: flex; gap: 10px; margin-top: 4px; }
.kl-btn {
  flex: 1; padding: 9px 12px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.2);
  color: #ccc; border-radius: 7px; cursor: pointer;
  font-size: 13px; font-weight: bold; transition: all 0.15s;
}
.kl-btn:hover:not(:disabled) { background: rgba(255,255,255,0.1); }
.kl-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.kl-btn-active { background: rgba(100,160,255,0.18); border-color: #6aaeff; color: #6aaeff; }
.kl-error {
  margin-top: 8px; font-size: 12px; color: #ff6b6b;
  background: rgba(255,80,80,0.1); border-radius: 4px; padding: 6px 8px;
}
.kl-success { margin-top: 8px; font-size: 12px; color: #6bff6b; }

/* Confirmation modal */
.confirm-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 2000;
  backdrop-filter: blur(2px);
}
.confirm-modal {
  background: #ffffff; border: 1px solid #d0d7de; border-radius: 10px;
  padding: 24px; width: 340px; display: flex; flex-direction: column; gap: 14px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.2);
}
.confirm-title { font-size: 15px; font-weight: bold; color: #1f2328; }
.confirm-body  { font-size: 13px; color: #57606a; }
.confirm-actions { display: flex; justify-content: flex-end; gap: 10px; }
.btn-secondary {
  padding: 7px 14px; background: #f6f8fa; border: 1px solid #d0d7de;
  color: #1f2328; border-radius: 6px; cursor: pointer; font-size: 12px;
}
.btn-secondary:hover { background: #e8ecf0; }

</style>
