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
          :disabled="sessionActive || experimentActive"
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
            :disabled="sessionActive || experimentActive"
          >Recommendation</button>
          <button
            class="mode-btn"
            :class="{ 'mode-btn-active': mode === 'colearning' }"
            @click="mode = 'colearning'"
            :disabled="sessionActive || experimentActive"
          >Co-Learning</button>
        </div>
        <div class="tl-start-row">
          <button
            class="scenario-btn scenario-btn-load"
            :disabled="!selectedScenario || sessionActive || sessionLoading || experimentActive"
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
          <button class="module-btn module-btn-reflection" @click="openReflection" :disabled="experimentActive">
            <span class="module-label">Reflexionsmodul</span>
          </button>
          <button class="module-btn module-btn-test" @click="startTestProtocol" :disabled="sessionActive || experimentActive">
            <span class="module-label">Testprotokoll</span>
          </button>
          <button class="module-btn module-btn-test" @click="showExperiment = true" :disabled="sessionActive || experimentActive"
            :class="{ active: experimentActive }">
            <span class="module-label">Experiment</span>
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

  <!-- ── Experiment login modal ── -->
  <div v-if="showExperiment && !experimentActive" class="reflection-overlay">
    <div class="reflection-modal" style="max-width:420px; width:90vw;">
      <div class="reflection-title">🧪 Experiment — Anmeldung</div>
      <div class="reflection-subtitle" style="margin-top:8px;">Bitte gib dein Kürzel ein. Das Experiment startet automatisch mit 6 Szenarien (3 pro Modus) in zufälliger Reihenfolge.</div>
      <div class="kl-section-label" style="margin-top:12px;">Nutzerkennung:</div>
      <input v-model="experimentAcronym" class="login-input" placeholder="Kürzel" style="width:100%;box-sizing:border-box;" @keyup.enter="launchExperiment" />
      <div class="reflection-actions" style="margin-top:16px;">
        <button class="scenario-btn scenario-btn-end" @click="showExperiment = false">Abbrechen</button>
        <button class="scenario-btn scenario-btn-load" :disabled="!experimentAcronym.trim()" @click="launchExperiment">Starten ▶</button>
      </div>
    </div>
  </div>

  <!-- ── Experiment scenario intro ── -->
  <div v-if="showExperimentIntro" class="reflection-overlay">
    <div class="reflection-modal" style="max-width:640px; width:90vw;">
      <div class="reflection-title">📋 Szenario-Einführung — Run {{ experimentRunIndex + 1 }}/6</div>
      <div class="reflection-subtitle" style="white-space:pre-line; line-height:1.7; margin-top:8px; font-size:15px;">
        {{ SCENARIO_INTROS[experimentRuns[experimentRunIndex]?.scenario] }}
      </div>
      <div class="reflection-actions" style="margin-top:20px;">
        <button class="scenario-btn scenario-btn-load" @click="showExperimentIntro = false; runNextExperimentSession()">
          Szenario starten ▶
        </button>
      </div>
    </div>
  </div>

  <!-- ── Experiment running banner ── -->
  <div v-if="experimentActive && experimentStep === 2" class="test-banner">
    <div class="test-banner-info">
      <span style="font-weight:600;">Experiment {{ experimentRunIndex + 1 }}/6</span>
      <span style="margin-left:12px;">{{ experimentRuns[experimentRunIndex]?.name }}</span>
      <span class="test-badge" :style="experimentRuns[experimentRunIndex]?.mode === 'colearning' ? 'background:#4a90d9' : 'background:#7b5ea7'">
        {{ experimentRuns[experimentRunIndex]?.mode === 'colearning' ? 'Co-Learning' : 'Recommendation' }}
      </span>
      <span style="margin-left:12px; opacity:0.7;">Schritt {{ sessionStep }}</span>
    </div>
    <button class="test-banner-cancel" @click="closeExperiment" title="Experiment abbrechen">✕</button>
  </div>

  <!-- ── Experiment reflection (co-learning runs only) ── -->
  <div v-if="experimentActive && experimentStep === 3" class="reflection-overlay">
    <div class="reflection-modal">
      <div class="reflection-title">📋 Reflexionsfragen — Run {{ Math.min(experimentRunIndex + 1, 6) }}/6</div>
      <div v-for="(q, i) in experimentQuestions" :key="i" class="reflection-question">
        <div class="reflection-q-text">{{ q.text }}</div>
        <textarea v-model="experimentQuestions[i].answer" class="reflection-textarea" rows="3" placeholder="Ihre Antwort..."></textarea>
      </div>
      <div class="reflection-actions" style="margin-top:16px;">
        <button class="scenario-btn scenario-btn-load" :disabled="experimentQuestions.some(q => !q.answer.trim())" @click="submitExperimentReflection">
          Weiter ▶
        </button>
      </div>
    </div>
  </div>

  <!-- ── Experiment complete ── -->
  <div v-if="experimentActive && experimentStep === 4" class="reflection-overlay">
    <div class="reflection-modal" style="max-width:420px;">
      <div class="reflection-title">✅ Experiment abgeschlossen</div>
      <div class="reflection-subtitle" style="margin-top:8px;">Alle 6 Szenarien wurden erfolgreich durchgeführt und protokolliert. Vielen Dank für Ihre Teilnahme!</div>
      <div class="reflection-actions" style="margin-top:16px;">
        <button class="scenario-btn scenario-btn-load" @click="closeExperiment">Schliessen</button>
      </div>
    </div>
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
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useCardsStore } from '@/stores/cards'

const BRAIN_URL  = import.meta.env.VITE_RAILWAY_SIMU || 'http://localhost:5001'
const cardsStore = useCardsStore()

async function forceMapRefresh() {
  // Signal Angular to re-fetch transitions
  try {
    await fetch(`${BRAIN_URL}/control`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: 'reset' }),
    })
  } catch {}
}

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

// ── Experiment mode ──────────────────────────────────────────────────────────
const showExperiment        = ref<boolean>(false)
const experimentActive      = ref<boolean>(false)
const experimentStep        = ref<number>(0)   // 0=idle 1=login 2=running 3=reflect 4=done
const experimentAcronym     = ref<string>('')
const experimentRunIndex    = ref<number>(0)   // 0–5
const experimentRuns        = ref<Array<{scenario: string, mode: string, name: string}>>([])
const experimentQuestions   = ref<Array<{text: string, answer: string}>>([])
let   experimentPollTimer   = null as any
const showExperimentIntro   = ref<boolean>(false)

const EXPERIMENT_SCENARIOS = [
  { id: 'scenario1', name: 'Szenario 1 — Kreuzungskonflikt' },
  { id: 'scenario2', name: 'Szenario 2 — Fahrt auf Sichtweite' },
  { id: 'scenario3', name: 'Szenario 3 — Zugreihenfolge' },
]

const SCENARIO_INTROS: Record<string, string> = {
  scenario1: `Durch die Verspätung des Zuges IC 301 kann die geplante Zugkreuzung mit der S 420 nicht stattfinden, da nun zwei Züge zur gleichen Zeit zur Einbahnpassage kommen. Nun muss entschieden werden, welcher Zug Priorität bekommt.`,
  scenario3: `Durch technische Störungen bei den Zügen S 17 und S 18 hat sich die ursprünglich geplante Zugreihenfolge auf dem gemeinsamen Streckenabschnitt verschoben. S 17 musste wegen eines Hindernisses auf der Strecke anhalten, und S 18 war von einer Signalstörung betroffen.\n\nDurch diese Verzögerungen kommt es nun zu einem Dispositionskonflikt: Alle drei Züge — S 17, S 18 und IC 3 — treffen annähernd gleichzeitig im Kreuzungsbereich ein, sodass die Reihenfolge neu festgelegt werden muss. Beurteilen Sie die Situation und entscheiden Sie, welchem Zug Vorfahrt gewährt werden soll.`,

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
      forceMapRefresh()
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
  // If in experiment mode, close it entirely
  if (experimentActive.value) {
    closeExperiment()
    return
  }
  clearRailwayNotifications()
  try {
    await fetch(`${BRAIN_URL}/session/stop`, { method: 'POST' })
  } catch {}
  forceMapRefresh()
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

onMounted(() => {
  fetchScenarios()
  // Restore experiment state after page refresh
  try {
    const saved = sessionStorage.getItem('experiment_state')
    if (saved) {
      const s = JSON.parse(saved)
      if (s.experimentActive && s.experimentStep < 4) {
        experimentActive.value   = s.experimentActive
        experimentStep.value     = s.experimentStep
        experimentRunIndex.value = s.experimentRunIndex
        experimentRuns.value     = s.experimentRuns
        experimentAcronym.value  = s.experimentAcronym
        // Resume polling if was running
        if (s.experimentStep === 2) runNextExperimentSession()
      }
    }
  } catch {}
})
onUnmounted(() => { stopPolling() })

// Persist experiment state across refreshes
watch([experimentActive, experimentStep, experimentRunIndex], () => {
  if (experimentActive.value) {
    sessionStorage.setItem('experiment_state', JSON.stringify({
      experimentActive:   experimentActive.value,
      experimentStep:     experimentStep.value,
      experimentRunIndex: experimentRunIndex.value,
      experimentRuns:     experimentRuns.value,
      experimentAcronym:  experimentAcronym.value,
    }))
  } else {
    sessionStorage.removeItem('experiment_state')
  }
})

// ── Experiment mode functions ─────────────────────────────────────────────

function buildExperimentRuns(firstMode: string) {
  const other = firstMode === 'colearning' ? 'recommendation' : 'colearning'
  const shuffle = (arr: typeof EXPERIMENT_SCENARIOS) => [...arr].sort(() => Math.random() - 0.5)
  return [
    ...shuffle(EXPERIMENT_SCENARIOS).map(s => ({ scenario: s.id, mode: firstMode, name: s.name })),
    ...shuffle(EXPERIMENT_SCENARIOS).map(s => ({ scenario: s.id, mode: other,     name: s.name })),
  ]
}

async function launchExperiment() {
  if (!experimentAcronym.value.trim()) return
  const firstMode = Math.random() < 0.5 ? 'colearning' : 'recommendation'
  experimentRuns.value     = buildExperimentRuns(firstMode)
  experimentRunIndex.value = 0
  experimentActive.value   = true
  showExperiment.value     = false
  sessionActive.value      = false
  experimentStep.value     = 2
  const firstRun = experimentRuns.value[0]
  if (firstRun && SCENARIO_INTROS[firstRun.scenario]) {
    showExperimentIntro.value = true
  } else {
    await runNextExperimentSession()
  }
}

async function runNextExperimentSession() {
  if (experimentRunIndex.value >= 6) { experimentStep.value = 4; return }
  const run = experimentRuns.value[experimentRunIndex.value]
  clearRailwayNotifications()
  try {
    const res = await fetch(`${BRAIN_URL}/session/start`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_ids: [run.scenario], mode: run.mode, acronym: experimentAcronym.value }),
    })
    const data = await res.json()
    if (!data.session_id) { error.value = 'Experiment: Sitzung konnte nicht gestartet werden.'; return }
    sessionActive.value = true
    try {
      await fetch(`${BRAIN_URL}/control`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: 'speed', value: 0.5 }) })
    } catch {}
    if (experimentPollTimer) clearInterval(experimentPollTimer)
    experimentPollTimer = setInterval(async () => {
      if (experimentStep.value !== 2) { clearInterval(experimentPollTimer); return }
      try {
        const sr = await fetch(`${BRAIN_URL}/session/status`)
        const sd = await sr.json()
        sessionStep.value = sd.step ?? 0
        if (sd.state === 'complete') {
          clearInterval(experimentPollTimer)
          clearRailwayNotifications()
          sessionActive.value = false
          if (run.mode === 'colearning') {
            const shuffled = [...ALL_QUESTIONS].sort(() => Math.random() - 0.5)
            experimentQuestions.value = shuffled.slice(0, 2).map((t: string) => ({ text: t, answer: '' }))
            experimentStep.value = 3
          } else {
            experimentRunIndex.value++
            experimentStep.value = 2
            const nextRun = experimentRuns.value[experimentRunIndex.value]
            if (nextRun && SCENARIO_INTROS[nextRun.scenario]) {
              showExperimentIntro.value = true
            } else {
              await runNextExperimentSession()
            }
          }
        }
      } catch {}
    }, 2000)
  } catch { error.value = 'Experiment: Verbindungsfehler.' }
}

async function submitExperimentReflection() {
  experimentRunIndex.value++
  experimentStep.value = 2
  const nextRun = experimentRuns.value[experimentRunIndex.value]
  if (nextRun && SCENARIO_INTROS[nextRun.scenario]) {
    showExperimentIntro.value = true
  } else {
    await runNextExperimentSession()
  }
}

function closeExperiment() {
  if (experimentPollTimer) clearInterval(experimentPollTimer)
  experimentActive.value = false
  experimentStep.value   = 0
  showExperiment.value   = false
  sessionActive.value    = false
  clearRailwayNotifications()
}
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
