<template>
  <section class="cab-panel scenario-panel">
    <div class="scenario-header">
      <span class="scenario-header-title">Szenario-Loader</span>
      <button
        class="panel-expand-btn"
        @click="expandPanel"
        title="Panel vergrößern"
      >⬆</button>
    </div>

    <div class="scenario-body">

      <!-- COL 1: Szenario selection -->
      <div class="tl-col tl-col-scenario">
        <div class="tl-col-label">Szenario</div>
        <select
          v-model="selectedScenario"
          class="scenario-select"
          :disabled="sessionActive"
          @change="previewScenarioMap(selectedScenario)"
        >
          <option value="" disabled>— Auswählen —</option>
          <option v-for="s in scenarios" :key="s.id" :value="s.id">
            {{ s.name }}
          </option>
        </select>
        <div v-if="sessionActive" class="scenario-active-label">
          🎬 {{ activeScenarioName }} — Schritt {{ sessionStep }}
          <span v-if="sessionState === 'paused_for_decision'" class="scenario-decision-badge">
            ⚠ Entscheidung erforderlich
          </span>
        </div>
        <div v-if="error" class="scenario-error">{{ error }}</div>
      </div>

      <div class="tl-divider" />

      <!-- COL 2: Modus + Start -->
      <div class="tl-col tl-col-actions">
        <div class="tl-col-label">Modus</div>
        <div class="mode-toggle">
          <button
            class="mode-btn"
            :class="{ 'mode-btn-active': mode === 'recommendation' }"
            @click="mode = 'recommendation'"
            :disabled="sessionActive"
          >Recommendation</button>
          <button
            class="mode-btn"
            :class="{ 'mode-btn-active': mode === 'colearning' }"
            @click="mode = 'colearning'"
            :disabled="sessionActive"
          >Co-Learning</button>
        </div>
        <div class="tl-start-row">
          <button
            class="scenario-btn scenario-btn-load"
            :disabled="!selectedScenario || sessionActive || sessionLoading"
            @click="loadScenario"
            style="width: auto; align-self: flex-start; white-space: nowrap;"
          >▶ Laden &amp; Starten</button>
          <button
            v-if="sessionActive"
            class="scenario-btn scenario-btn-end"
            @click="endSession"
            style="width: auto; align-self: flex-start; white-space: nowrap;"
          >✕ Beenden</button>
        </div>
      </div>

      <div class="tl-divider" />

      <!-- COL 3: Module -->
      <div class="tl-col tl-col-modules">
        <div class="tl-col-label">Module</div>
        <div class="module-buttons">
          <button class="module-btn module-btn-login" @click="openLogin">
            <span class="module-label">Nutzerkennung</span>
          </button>
          <button class="module-btn module-btn-reflection" @click="openReflection">
            <span class="module-label">Reflexionsmodul</span>
          </button>
          <button class="module-btn module-btn-test" @click="startTestProtocol" :disabled="sessionActive">
            <span class="module-label">Testprotokoll</span>
          </button>
        </div>
        <div v-if="acronymSaved" class="acronym-badge">
          ✓ <strong>{{ acronym }}</strong>
        </div>
      </div>

    </div>
  <!-- User Login Modal -->
  <div v-if="showLogin" class="reflection-overlay" @click.self="showLogin = false">
    <div class="login-modal">
      <div class="login-title">👤 Nutzerkennung eingeben</div>
      <div class="login-subtitle">
        Bitte gib dein persönliches Kürzel ein, bevor du mit dem Test beginnst.
      </div>
      <input
        v-model="loginInput"
        class="login-input"
        placeholder="z.B. JM"
        maxlength="10"
        @keyup.enter="confirmLogin"
        autofocus
      />
      <div class="login-actions">
        <button class="scenario-btn scenario-btn-end" @click="showLogin = false">Abbrechen</button>
        <button class="scenario-btn scenario-btn-load" :disabled="!loginInput.trim()" @click="confirmLogin">
          Bestätigen
        </button>
      </div>
      <div v-if="loginSaved" class="login-saved">✓ Angemeldet als {{ acronym }}</div>
    </div>
  </div>

  <!-- Floating test protocol banner (step 2 only) -->
  <div v-if="testStep === 2" class="test-banner">
    🧪 Testprotokoll läuft — Schritt 2/3
    <span style="opacity:0.7; font-size:10px; margin-left:8px;">
      Führe das Szenario durch und triff eine Entscheidung im Assistenten-Tab.
    </span>
    <button class="test-banner-cancel" @click="closeTestProtocol">✕</button>
  </div>

  <!-- Scenario intro popup (testprotokoll only) — same style as testprotokoll modal -->
  <div v-if="showTestIntro" class="reflection-overlay">
    <div class="reflection-modal" style="max-width: 640px; width: 90vw;">
      <div class="reflection-title">📋 Szenario-Einführung</div>
      <div class="reflection-subtitle" style="white-space: pre-line; line-height: 1.7; margin-top: 8px; font-size: 24px;">{{ SCENARIO_INTROS[testScenario] }}</div>
      <div class="reflection-actions" style="margin-top: 20px;">
        <button class="scenario-btn scenario-btn-end"
          @click="showTestIntro = false; showTestProtocol = true; testStep = 1">
          Abbrechen
        </button>
        <button class="scenario-btn scenario-btn-load"
          @click="showTestIntro = false; startTestSession()">
          Szenario starten ▶
        </button>
      </div>
    </div>
  </div>

  <!-- Test Protocol Modal -->
  <div v-if="showTestProtocol" class="reflection-overlay">
    <div class="reflection-modal" style="width:520px;">
      <!-- Step indicator -->
      <div class="test-steps">
        <span :class="testStep >= 1 ? 'test-step-active' : 'test-step'">1 Anmeldung</span>
        <span class="test-step-arrow">→</span>
        <span :class="testStep >= 2 ? 'test-step-active' : 'test-step'">2 Szenario</span>
        <span class="test-step-arrow">→</span>
        <span :class="testStep >= 3 ? 'test-step-active' : 'test-step'">3 Reflexion</span>
        <span class="test-step-arrow">→</span>
        <span :class="testStep >= 4 ? 'test-step-active' : 'test-step'">4 Protokoll</span>
      </div>

      <!-- Step 1: Login + Mode -->
      <div v-if="testStep === 1">
        <div class="reflection-title">🧪 Testprotokoll — Anmeldung</div>
        <div class="reflection-subtitle">Bitte gib dein Kürzel ein und wähle den Modus.</div>

        <div class="kl-section-label" style="color:#57606a;">Nutzerkennung:</div>
        <input v-model="loginInput" class="login-input" placeholder="Kürzel (z.B. JM01)"
          maxlength="10" style="width:100%; box-sizing:border-box;" />

        <div class="kl-section-label" style="color:#57606a; margin-top:12px;">Modus:</div>
        <div class="mode-toggle" style="gap:8px;">
          <button
            class="mode-btn"
            :class="{ 'mode-btn-active': testMode === 'recommendation' }"
            @click="testMode = 'recommendation'"
            style="flex:1; border:1px solid #d0d7de; background:#f6f8fa; color:#1f2328;"
            :style="testMode === 'recommendation' ? 'border-color:#0969da; background:#dbeafe; color:#0969da; font-weight:bold;' : ''"
          >Recommendation</button>
          <button
            class="mode-btn"
            :class="{ 'mode-btn-active': testMode === 'colearning' }"
            @click="testMode = 'colearning'"
            style="flex:1; border:1px solid #d0d7de; background:#f6f8fa; color:#1f2328;"
            :style="testMode === 'colearning' ? 'border-color:#0969da; background:#dbeafe; color:#0969da; font-weight:bold;' : ''"
          >Co-Learning</button>
        </div>

        <div class="kl-section-label" style="color:#57606a; margin-top:12px;">Szenario:</div>
        <select v-model="testScenario" class="scenario-select" style="width:100%; box-sizing:border-box;">
          <option value="" disabled>— Szenario auswählen —</option>
          <option v-for="s in scenarios" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>

        <div class="reflection-actions" style="margin-top:16px;">
          <button class="scenario-btn scenario-btn-end" @click="closeTestProtocol">Abbrechen</button>
          <button class="scenario-btn scenario-btn-load"
            :disabled="!loginInput.trim() || !testMode || !testScenario"
            @click="testLogin">
            Weiter ▶
          </button>
        </div>
      </div>

      <!-- Step 2: Hidden — show floating banner instead, modal closes -->
      <div v-if="testStep === 2" style="display:none"></div>

      <!-- Step 3: Reflection -->
      <div v-if="testStep === 3">
        <div class="reflection-title">🧪 Testprotokoll — Reflexion</div>
        <div class="reflection-subtitle">Szenario abgeschlossen. Bitte beantworte die folgenden Fragen.</div>
        <div v-for="(q, i) in activeQuestions" :key="i" class="reflection-question">
          <div class="question-text">{{ i + 1 }}. {{ q.text }}</div>
          <textarea v-model="q.answer" class="question-input" rows="3" placeholder="Deine Antwort..." />
        </div>
        <div class="reflection-actions">
          <button class="scenario-btn scenario-btn-load" @click="submitTestReflection">
            Absenden & Protokoll speichern
          </button>
        </div>
      </div>

      <!-- Step 4: Complete -->
      <div v-if="testStep === 4">
        <div class="reflection-title">✓ Testprotokoll abgeschlossen</div>
        <div class="reflection-subtitle">Das Protokoll wurde gespeichert.</div>
        <div v-if="savedLogFile" style="margin-top:12px; font-family:monospace; font-size:12px;
          background:#f6f8fa; border:1px solid #d0d7de; border-radius:6px; padding:10px; color:#1f2328;">
          📄 {{ savedLogFile }}
        </div>
        <div v-if="savedLogData" style="margin-top:12px;">
          <div style="font-size:12px; font-weight:bold; margin-bottom:6px; color:#57606a;">Protokollinhalt:</div>
          <pre style="font-size:10px; background:#f6f8fa; border:1px solid #d0d7de; border-radius:6px;
            padding:10px; overflow:auto; max-height:200px; color:#1f2328;">{{ savedLogData }}</pre>
        </div>
        <div class="reflection-actions">
          <button class="scenario-btn scenario-btn-load" @click="closeTestProtocol">Schließen</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Reflection Modal -->
  <div v-if="showReflection" class="reflection-overlay" @click.self="closeReflection">
    <div class="reflection-modal">
      <div class="reflection-title">💬 Reflexionsmodul</div>
      <div class="reflection-subtitle">
        Bitte beantworte die folgenden Fragen kurz und ehrlich.
      </div>

      <div v-for="(q, i) in activeQuestions" :key="i" class="reflection-question">
        <div class="question-text">{{ i + 1 }}. {{ q.text }}</div>
        <textarea
          v-model="q.answer"
          class="question-input"
          placeholder="Deine Antwort..."
          rows="3"
        />
      </div>

      <div class="reflection-actions">
        <button class="scenario-btn scenario-btn-end" @click="closeReflection">
          Abbrechen
        </button>
        <button class="scenario-btn scenario-btn-load" @click="submitReflection">
          Absenden
        </button>
      </div>

      <div v-if="reflectionSaved" class="reflection-saved">
        ✓ Antworten gespeichert.
      </div>
    </div>
  </div>
  </section>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useCardsStore } from '@/stores/cards'

const BRAIN_URL  = import.meta.env.VITE_RAILWAY_SIMU || 'http://localhost:5001'
const cardsStore = useCardsStore()

function clearRailwayNotifications() {
  // Remove all Railway entity cards from the notification panel
  const toRemove = (cardsStore._cards as any[]).filter(
    (c: any) => c.entityRecipients?.includes('Railway') || c.process === 'cabProcess'
  )
  toRemove.forEach((c: any) => cardsStore.remove(c))
}

const scenarios          = ref<{ id: string; name: string }[]>([])
const selectedScenario   = ref<string>('')
const sessionActive      = ref<boolean>(false)
const sessionLoading     = ref<boolean>(false)
const mode               = ref<string>('recommendation')
const acronym            = ref<string>('')

// Reflection module
const showReflection     = ref<boolean>(false)
const showLogin          = ref<boolean>(false)
const loginInput         = ref<string>('')
const loginSaved         = ref<boolean>(false)
const acronymSaved       = ref<boolean>(false)

// Test protocol
const showTestProtocol   = ref<boolean>(false)
const testStep           = ref<number>(1)
const testMode           = ref<string>('')
const testScenario       = ref<string>('')
const showTestIntro      = ref<boolean>(false)

const SCENARIO_INTROS: Record<string, string> = {
  scenario1: `Durch die Verspätung des Zuges IC 301 kann die geplante Zugkreuzung mit der S 420 nicht stattfinden, da nun zwei Züge zur gleichen Zeit zur Einbahnpassage kommen. Nun muss entschieden werden, welcher Zug Priorität bekommt.`,
  scenario2: `Im Bereich Rüthi wurde eine Unregelmässigkeit der Fahrbahn festgestellt. Für den betroffenen Abschnitt gilt bis auf Weiteres eine Geschwindigkeitsbegrenzung von 40 km/h.

Dadurch verspätet sich P 205, wodurch ein Konflikt mit P 312 und dem Güterzug G 501 auf dem Einspurabschnitt entsteht. Beurteilen Sie die Situation und formulieren Sie Ihre Dispositionshypothese. Welche Zugreihenfolge bzw. Massnahme würden Sie wählen?`,
}
const savedLogFile       = ref<string>('')
const savedLogData       = ref<string>('')
const testStartedAt      = ref<string>('')
const activeScenarioName = ref<string>('')
let testPollTimer: any   = null
const reflectionSaved    = ref<boolean>(false)
const activeQuestions    = ref<{ text: string; answer: string }[]>([])
const sessionStep        = ref<number>(0)
const sessionState       = ref<string>('idle')
const ALL_QUESTIONS = [
  'Auf welche Logik habe ich mich gestützt?',
  'Welche Informationen fehlten, die mir geholfen hätten?',
  'Welche Faktoren habe ich für meine Entscheidung berücksichtigt?',
  'Was ist die wichtigste Erkenntnis für das nächste Mal?',
  'Gab es ein Bauchgefühl, das ich ignoriert habe?',
]
const error              = ref<string>('')

let pollInterval: ReturnType<typeof setInterval> | null = null

// ── Test Protocol ────────────────────────────────────────────────────────────

function startTestProtocol() {
  testStep.value         = 1
  testMode.value         = ''
  testScenario.value     = ''
  savedLogFile.value     = ''
  savedLogData.value     = ''
  loginInput.value       = acronym.value
  showTestProtocol.value = true
}

function closeTestProtocol() {
  showTestProtocol.value = false
  showTestIntro.value    = false
  if (testPollTimer) { clearInterval(testPollTimer); testPollTimer = null }
}

async function testLogin() {
  if (!loginInput.value.trim()) return
  acronym.value       = loginInput.value.trim().toUpperCase()
  acronymSaved.value  = true
  testStartedAt.value = new Date().toISOString()

  // Show intro popup if this scenario has a description
  if (SCENARIO_INTROS[testScenario.value]) {
    showTestProtocol.value = false  // close step 1 modal so intro is visible
    showTestIntro.value    = true
    return
  }
  await startTestSession()
}

async function startTestSession() {
  // Auto-start the test scenario in current mode
  try {
    const res  = await fetch(`${BRAIN_URL}/session/start`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        scenario_ids: [testScenario.value],
        mode:         testMode.value,
        acronym:      acronym.value,
      }),
    })
    const data = await res.json()
    sessionActive.value      = true
    activeScenarioName.value = data.scenario_name || 'Testszenario'
    // Set speed to 0.5x for test protocol
    try {
      await fetch(`${BRAIN_URL}/control`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: 'speed', value: 0.5 }),
      })
    } catch {}
    testStep.value = 2
    showTestProtocol.value = false  // close modal so user can interact with the interface

    // Poll for scenario completion
    if (testPollTimer) { clearInterval(testPollTimer); testPollTimer = null }
    testPollTimer = setInterval(async () => {
      // Stop immediately if we've already advanced past step 2
      if (testStep.value !== 2) {
        clearInterval(testPollTimer); testPollTimer = null
        return
      }
      try {
        const sRes  = await fetch(`${BRAIN_URL}/session/status`)
        const sData = await sRes.json()
        if (sData.state === 'complete') {
          clearInterval(testPollTimer); testPollTimer = null
          clearRailwayNotifications()
          // Auto-advance to reflection — only once
          if (testStep.value === 2) {
            const shuffled = [...ALL_QUESTIONS].sort(() => Math.random() - 0.5)
            activeQuestions.value = shuffled.slice(0, 2).map(text => ({ text, answer: '' }))
            testStep.value = 3
            showTestProtocol.value = true  // reopen modal for reflection
          }
        }
      } catch {}
    }, 2000)
  } catch {
    error.value = 'Fehler beim Starten des Testszenarios.'
  }
}

async function submitTestReflection() {
  // Collect reflection answers
  const reflectionAnswers = activeQuestions.value.map((q, i) => ({
    frage:   q.text,
    antwort: q.answer,
  }))

  // Get last decision from Flask
  try {
    const res  = await fetch(`${BRAIN_URL}/experiment/log`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        participant_id:     acronym.value,
        started_at:         testStartedAt.value,
        reflection_answers: reflectionAnswers,
      }),
    })
    const data = await res.json()
    savedLogFile.value = data.datei || ''
    savedLogData.value = JSON.stringify(data.log, null, 2)
    sessionActive.value = false
    testStep.value = 4
  } catch {
    error.value = 'Fehler beim Speichern des Protokolls.'
  }
}

function openLogin() {
  loginInput.value = acronym.value
  loginSaved.value = false
  showLogin.value  = true
}

function confirmLogin() {
  if (!loginInput.value.trim()) return
  acronym.value      = loginInput.value.trim().toUpperCase()
  acronymSaved.value = true
  loginSaved.value   = true
  setTimeout(() => { showLogin.value = false }, 1200)
}

function openReflection() {
  // Pick 2 random questions
  const shuffled = [...ALL_QUESTIONS].sort(() => Math.random() - 0.5)
  activeQuestions.value = shuffled.slice(0, 2).map((text, i) => ({
    text,
    answer: '',
  }))
  reflectionSaved.value = false
  showReflection.value  = true
}

function closeReflection() {
  showReflection.value = false
}

async function submitReflection() {
  const answers = activeQuestions.value.map((q, i) => ({
    question_index: ALL_QUESTIONS.indexOf(q.text),
    question_text:  q.text,
    answer:         q.answer,
  }))
  try {
    await fetch(`${BRAIN_URL}/reflection`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        session_id: '',  // will be filled by server from active session
        acronym:    acronym.value,
        answers,
      }),
    })
    reflectionSaved.value = true
    setTimeout(() => { showReflection.value = false }, 2000)
  } catch {
    reflectionSaved.value = false
  }
}

function expandPanel() {
  // Find the timeline panel and reset to comfortable height
  const panel = document.querySelector('.cab-timelines') as HTMLElement
  if (panel) panel.style.height = '216px'
}

// Update Angular map preview when scenario is selected
async function previewScenarioMap(scenarioId: string) {
  if (!scenarioId) return
  try {
    // Store selected scenario in Flask so /transitions returns its grid
    await fetch(`${BRAIN_URL}/scenario/select`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ scenario_id: scenarioId }),
    })
    // Trigger Angular to re-fetch transitions (now returns the scenario grid)
    await fetch(`${BRAIN_URL}/control`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ command: 'reset' }),
    })
  } catch {}
}

async function fetchScenarios() {
  try {
    const res = await fetch(`${BRAIN_URL}/scenarios`)
    scenarios.value = await res.json()
    if (scenarios.value.length > 0) {
      selectedScenario.value = scenarios.value[0].id
    }
  } catch {
    error.value = 'Could not reach Flask brain.'
  }
}

async function loadScenario() {
  if (!selectedScenario.value) return
  clearRailwayNotifications()
  error.value = ''
  try {
    const res  = await fetch(`${BRAIN_URL}/session/start`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ scenario_ids: [selectedScenario.value], mode: mode.value, acronym: acronym.value }),
    })
    const data = await res.json()
    if (data.session_id) {
      sessionActive.value      = true
      activeScenarioName.value = data.scenario_name || selectedScenario.value
      // Reset Angular ZWL map so it reloads grid for the new scenario
      try {
        await fetch(`${BRAIN_URL}/control`, {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ command: 'reset' }),
        })
      } catch {}
      startPolling()
    } else {
      error.value = data.error || 'Failed to start scenario.'
    }
  } catch {
    error.value = 'Failed to connect to Flask brain.'
  } finally {
    sessionLoading.value = false
  }
}

async function endSession() {
  clearRailwayNotifications()
  try {
    await fetch(`${BRAIN_URL}/session/stop`, { method: 'POST' })
  } catch {}
  sessionActive.value = false
  sessionState.value  = 'idle'
  sessionStep.value   = 0
  stopPolling()
}

function startPolling() {
  pollInterval = setInterval(async () => {
    try {
      const res  = await fetch(`${BRAIN_URL}/session/status`)
      const data = await res.json()
      sessionStep.value  = data.step ?? 0
      sessionState.value = data.state ?? 'idle'
      if (data.state === 'complete') {
        clearRailwayNotifications()
        sessionActive.value = false
        stopPolling()
      }
    } catch {}
  }, 2000)
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

onMounted(() => { fetchScenarios() })
onUnmounted(() => { stopPolling() })
</script>

<style scoped>
.scenario-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 100px;
  overflow: hidden;
}
.scenario-panel:empty,
.scenario-body:empty { display: flex !important; min-height: 100px; }

.scenario-header {
  padding: 8px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  flex-shrink: 0;
}

.scenario-header-title {
  font-weight: bold;
  font-size: 13px;
  opacity: 0.9;
}



.scenario-list {
  display: flex;
  flex-direction: row;
  gap: 8px;
  flex: 1;
  overflow-x: auto;
}

.scenario-item {
  display: flex;
  flex-direction: column;
  padding: 8px 14px;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 6px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
  background: rgba(255,255,255,0.04);
}
.scenario-item:hover { background: rgba(255,255,255,0.08); }
.scenario-item-selected {
  border-color: #6aaeff;
  background: rgba(100,160,255,0.12);
}
.scenario-item-name {
  font-size: 12px;
  font-weight: bold;
  white-space: nowrap;
}
.scenario-item-id {
  font-size: 10px;
  opacity: 0.5;
  margin-top: 2px;
  white-space: nowrap;
}
.scenario-empty {
  font-size: 12px;
  opacity: 0.5;
}

.scenario-actions {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.scenario-btn {
  padding: 6px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  font-weight: bold;
  white-space: nowrap;
}
.scenario-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.scenario-btn-load {
  background: #2d6abf;
  color: #fff;
}
.scenario-btn-load:hover:not(:disabled) { background: #3a7fd4; }

.scenario-btn-end {
  background: #6a2d2d;
  color: #fff;
}
.scenario-btn-end:hover { background: #8a3a3a; }

.scenario-active-label {
  font-size: 12px;
  color: #6aaeff;
  display: flex;
  align-items: center;
  gap: 10px;
}

.scenario-decision-badge {
  background: rgba(220,50,50,0.2);
  color: #ff6b6b;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: bold;
}

.scenario-error {
  font-size: 11px;
  color: #ff6b6b;
}

.mode-selector {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 4px;
}
.mode-label {
  font-size: 11px;
  opacity: 0.6;
  font-weight: bold;
}
.mode-toggle {
  display: flex;
  gap: 6px;
}
.mode-btn {
  padding: 5px 12px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.15);
  color: #ccc;
  border-radius: 6px;
  cursor: pointer;
  font-size: 11px;
  white-space: nowrap;
  transition: all 0.15s;
}
.mode-btn:hover:not(:disabled) { background: rgba(255,255,255,0.1); }
.mode-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.mode-btn-active {
  background: rgba(100,160,255,0.15);
  border-color: #6aaeff;
  color: #6aaeff;
  font-weight: bold;
}

/* Acronym */


/* Reflection */
.scenario-btn-reflection { background: rgba(160,100,255,0.2); color: #c084fc; border-color: #c084fc; }
.scenario-btn-reflection:hover { background: rgba(160,100,255,0.3); }

.reflection-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
  backdrop-filter: blur(2px);
}
.reflection-modal {
  background: #ffffff; border: 1px solid #d0d7de;
  border-radius: 12px; padding: 24px; width: 480px; max-width: 90vw;
  display: flex; flex-direction: column; gap: 14px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.18);
}
.reflection-title { font-size: 16px; font-weight: bold; color: #1f2328; }
.reflection-subtitle { font-size: 12px; color: #57606a; }
.reflection-question { display: flex; flex-direction: column; gap: 6px; }
.question-text { font-size: 13px; font-weight: bold; color: #1f2328; }
.question-input {
  padding: 8px 10px; background: #f6f8fa;
  border: 1px solid #d0d7de; border-radius: 6px;
  color: #1f2328; font-size: 12px; resize: vertical; font-family: inherit;
}
.question-input:focus { outline: none; border-color: #0969da; background: #fff; }
.reflection-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 4px; }
.reflection-saved { font-size: 12px; color: #2da44e; text-align: center; font-weight: bold; }

/* User login modal */
.login-modal {
  background: #ffffff; border: 1px solid #d0d7de;
  border-radius: 12px; padding: 24px; width: 360px; max-width: 90vw;
  display: flex; flex-direction: column; gap: 14px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.18);
}
.login-title { font-size: 16px; font-weight: bold; color: #1f2328; }
.login-subtitle { font-size: 12px; color: #57606a; }
.login-input {
  padding: 9px 12px; background: #f6f8fa;
  border: 1px solid #d0d7de; border-radius: 6px;
  color: #1f2328; font-size: 14px; font-family: inherit;
  text-transform: uppercase; letter-spacing: 2px;
}
.login-input:focus { outline: none; border-color: #0969da; background: #fff; }
.login-actions { display: flex; justify-content: flex-end; gap: 10px; }
.login-saved { font-size: 12px; color: #2da44e; font-weight: bold; }


/* -- 3-column horizontal layout -- */
.scenario-body {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  flex-wrap: wrap;
  gap: 0;
  padding: 8px 12px;
  flex: 1;
  overflow: auto;
  min-height: 0;
}
.tl-col {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 0 10px;
  overflow: hidden;
}
.tl-col-scenario { flex: 2; min-width: 0; }
.tl-col-actions  { flex: 2; min-width: 0; }
.tl-col-modules  { flex: 1.5; min-width: 110px; }
.tl-col-label {
  font-size: clamp(10px, 1.1vw, 13px);
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 1px;
  opacity: 0.75;
  margin-bottom: 4px;
}
.tl-divider {
  width: 1px;
  background: rgba(255,255,255,0.1);
  margin: 4px 0;
  flex-shrink: 0;
}
.tl-start-row {
  display: flex;
  gap: 6px;
  margin-top: 4px;
}

/* -- Module buttons -- */
.module-buttons { display: flex; flex-direction: column; gap: 5px; align-items: flex-start; }
.module-btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 5px 10px; width: auto; max-width: 100%;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 6px; cursor: pointer;
  font-size: clamp(10px, 1vw, 12px); font-weight: 500; color: #ccc;
  transition: all 0.15s; box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  white-space: nowrap;
}
.module-btn:hover:not(:disabled) { background: rgba(255,255,255,0.10); border-color: rgba(255,255,255,0.35); }
.module-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.module-icon { font-size: 14px; width: 18px; text-align: center; }
.module-label { font-weight: 500; }
.module-btn-login      { border-color: rgba(9,105,218,0.5);   color: #6aaeff; }
.module-btn-reflection { border-color: rgba(160,100,255,0.5); color: #c084fc; }
.module-btn-test       { border-color: rgba(217,119,6,0.5);   color: #fbbf24; }
.module-btn-login:hover:not(:disabled)      { background: rgba(9,105,218,0.1); }
.module-btn-reflection:hover:not(:disabled) { background: rgba(160,100,255,0.1); }
.module-btn-test:hover:not(:disabled)       { background: rgba(217,119,6,0.1); }

.panel-expand-btn {
  background: none; border: 1px solid rgba(255,255,255,0.2);
  color: rgba(255,255,255,0.5); border-radius: 4px;
  padding: 1px 6px; cursor: pointer; font-size: 10px;
  margin-left: auto;
}
.panel-expand-btn:hover { background: rgba(255,255,255,0.1); color: #fff; }
.scenario-header { display: flex; align-items: center; }
</style>
