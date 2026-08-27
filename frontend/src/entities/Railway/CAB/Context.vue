<template>
  <Context
    :tabs="[
      'Kartenansicht',
      'ZWL Diagramm'
    ]">
    <!-- Kartenansicht — Angular map view (DEFAULT, index 0) -->
    <div
      v-if="appStore.tab.context === 0"
      style="display: flex; flex-direction: column; width: 100%; height: 100%;"
    >
      <!-- Shared control bar (same as FlatlandMap) -->
      <div class="zwl-controls">
        <button class="ctrl-btn" @click="sendCommand('start')" :disabled="running">
          ▶ Start
        </button>
        <button class="ctrl-btn" @click="sendCommand('pause')" :disabled="!running">
          ⏸ Pause
        </button>
        <button class="ctrl-btn" @click="sendCommand('reset')">
          ↺ Zurücksetzen
        </button>
        <div class="ctrl-speed">
          <label>Tempo</label>
          <input
            type="range"
            :disabled="sessionLocked"
            min="0.5" max="5" step="0.5"
            v-model.number="speed"
            @change="setSpeed"
          />
          <span>{{ speed }}×</span>
        </div>
        <span class="zwl-step">Schritt {{ step }}</span>
      </div>

      <!-- ZWL iframe -->
      <div style="flex: 1; min-height: 0;">
        <iframe
          src="http://localhost:4200/map"
          style="width: 100%; height: 100%; border: none; border-radius: 0 0 8px 8px;"
          title="ZWL — Zeit-Weg-Linien Diagram"
        />
      </div>
    </div>
    <!-- ZWL Diagramm — Marey diagram (index 1) -->
    <div
      v-if="appStore.tab.context === 1"
      style="display: flex; flex-direction: column; width: 100%; height: 100%;"
    >
      <div style="flex: 1; min-height: 0; overflow: hidden; position: relative;">
        <iframe
          src="http://localhost:4200/marey"
          style="width: 200%; height: 200%; border: none; transform: scale(0.5); transform-origin: top left; display: block;"
          title="ZWL Diagramm"
        />
      </div>
    </div>
  </Context>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import Context from '@/components/organisms/CAB/Context.vue'
import FlatlandMap from './FlatlandMap.vue'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
const BRAIN_URL = import.meta.env.VITE_RAILWAY_SIMU || 'http://localhost:5001'

const running = ref(false)
const speed         = ref(1)
const sessionLocked = ref(false)

// Poll session state to lock speed during scenario runs
let _speedLockTimer: any
onMounted(() => {
  _speedLockTimer = setInterval(async () => {
    try {
      const r = await fetch(`${BRAIN_URL}/session/status`)
      const d = await r.json()
      sessionLocked.value = d.state === 'running' || d.state === 'paused_for_decision'
    } catch {}
  }, 1000)
})
onUnmounted(() => clearInterval(_speedLockTimer))
const step    = ref(0)

let stateInterval: ReturnType<typeof setInterval> | null = null

async function sendCommand(cmd: string) {
  try {
    await fetch(`${BRAIN_URL}/control`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ command: cmd }),
    })
    if (cmd === 'start')  running.value = true
    if (cmd === 'pause')  running.value = false
    if (cmd === 'reset')  { running.value = false; step.value = 0 }
  } catch (e) {
    console.error('Control error:', e)
  }
}

async function setSpeed() {
  try {
    await fetch(`${BRAIN_URL}/control`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ command: 'speed', value: speed.value }),
    })
  } catch {}
}

async function pollState() {
  try {
    const res  = await fetch(`${BRAIN_URL}/state`)
    const data = await res.json()
    step.value = data.step ?? 0
  } catch {}
}

onMounted(() => {
  stateInterval = setInterval(pollState, 1000)
})
onUnmounted(() => {
  if (stateInterval) clearInterval(stateInterval)
})
</script>

<style scoped>
.zwl-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(0,0,0,0.2);
  border-bottom: 1px solid rgba(255,255,255,0.08);
  flex-shrink: 0;
}

.ctrl-btn {
  padding: 4px 12px;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.2);
  color: #fff;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}
.ctrl-btn:hover:not(:disabled) { background: rgba(255,255,255,0.18); }
.ctrl-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.ctrl-speed {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}
.ctrl-speed input { width: 80px; }

.zwl-step {
  margin-left: 8px;
  font-size: 11px;
  opacity: 0.6;
}
</style>
