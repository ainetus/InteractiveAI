<template>
  <div class="flatland-wrapper">
    <!-- Live Flatland map image from Flask brain -->
    <div class="flatland-map-container">
      <img
        v-if="imageUrl"
        :src="imageUrl"
        class="flatland-image"
        alt="Flatland simulation"
      />
      <div v-else class="flatland-placeholder">
        Waiting for simulation...
      </div>

      <!-- Step counter overlay -->
      <div class="flatland-step-badge">
        Step {{ step }}
      </div>

      <!-- Conflict indicator overlay -->
      <div v-if="hasConflict" class="flatland-conflict-badge">
        ⚠ Conflict detected
      </div>
    </div>

    <!-- Simulation controls -->
    <div class="flatland-controls">
      <button class="ctrl-btn" @click="sendCommand('start')" :disabled="running">
        ▶ Start
      </button>
      <button class="ctrl-btn" @click="sendCommand('pause')" :disabled="!running">
        ⏸ Pause
      </button>
      <button class="ctrl-btn" @click="sendCommand('reset')">
        ↺ Reset
      </button>
      <div class="ctrl-speed">
        <label>Speed</label>
        <input
          type="range"
          min="0.5"
          max="5"
          step="0.5"
          v-model.number="speed"
          @change="setSpeed"
        />
        <span>{{ speed }}×</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

// Address of the Flask brain — set VITE_RAILWAY_SIMU in your .env
const BRAIN_URL = import.meta.env.VITE_RAILWAY_SIMU || 'http://localhost:5001'

const imageUrl   = ref<string>('')
const step       = ref<number>(0)
const running    = ref<boolean>(false)
const hasConflict = ref<boolean>(false)
const speed      = ref<number>(1)

let renderInterval: ReturnType<typeof setInterval> | null = null
let stateInterval: ReturnType<typeof setInterval> | null = null

// Poll the rendered image every 500ms
function startRenderPolling() {
  renderInterval = setInterval(() => {
    // Cache-bust with timestamp so the browser always fetches fresh
    imageUrl.value = `${BRAIN_URL}/render?t=${Date.now()}`
  }, 500)
}

// Poll state (step counter, conflict flag) every second
async function pollState() {
  try {
    const res = await fetch(`${BRAIN_URL}/state`)
    if (!res.ok) return
    const data = await res.json()
    step.value = data.step ?? 0
  } catch {
    // Brain not reachable yet — fail silently
  }
}

// Poll conflicts every 2 seconds to update the badge
async function pollConflicts() {
  try {
    const res = await fetch(`${BRAIN_URL}/conflicts`)
    if (!res.ok) return
    const data = await res.json()
    hasConflict.value = data.conflict !== null
  } catch {
    // fail silently
  }
}

async function sendCommand(command: string) {
  try {
    await fetch(`${BRAIN_URL}/control`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command }),
    })
    if (command === 'start') running.value = true
    if (command === 'pause') running.value = false
    if (command === 'reset') { running.value = false; step.value = 0 }
  } catch (e) {
    console.error('Control command failed:', e)
  }
}

async function setSpeed() {
  try {
    await fetch(`${BRAIN_URL}/control`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: 'speed', value: speed.value }),
    })
  } catch (e) {
    console.error('Speed command failed:', e)
  }
}

onMounted(() => {
  startRenderPolling()
  stateInterval = setInterval(() => {
    pollState()
    pollConflicts()
  }, 1000)
  // Initial state load
  pollState()
})

onUnmounted(() => {
  if (renderInterval) clearInterval(renderInterval)
  if (stateInterval)  clearInterval(stateInterval)
})
</script>

<style scoped>
.flatland-wrapper {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
  height: 100%;
}

.flatland-map-container {
  position: relative;
  flex: 1;
  background: #1a1a2e;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
}

.flatland-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.flatland-placeholder {
  color: #888;
  font-size: 14px;
}

.flatland-step-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  background: rgba(0,0,0,0.6);
  color: #fff;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-family: monospace;
}

.flatland-conflict-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(220, 50, 50, 0.85);
  color: #fff;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: bold;
}

.flatland-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 8px;
  background: rgba(255,255,255,0.05);
  border-radius: 8px;
}

.ctrl-btn {
  padding: 6px 14px;
  border: none;
  border-radius: 6px;
  background: #2d4a6e;
  color: #fff;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s;
}

.ctrl-btn:hover:not(:disabled) {
  background: #3a5f8a;
}

.ctrl-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.ctrl-speed {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  font-size: 13px;
  color: #ccc;
}

.ctrl-speed input[type='range'] {
  width: 100px;
}
</style>
