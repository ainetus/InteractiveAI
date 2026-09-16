<template>
  <section v-if="survey" class="survey p-6">
    <header v-show="!done">
      <h1>{{ $t('survey.title') }}</h1>
      <p>{{ $t('survey.intro') }}</p>
    </header>
    <!-- `v-show`, not `v-if`: the chainer starts its JSON download in the same
         task as the message that ends the chain, and unmounting the frame under
         it would cancel that download. -->
    <iframe v-show="!done" :src="url" :title="$t('survey.title')"></iframe>
    <Button v-show="!done" color="secondary" @click="leave">{{ $t('survey.skip') }}</Button>
    <div v-if="done" class="flex flex-center flex-col h-100">
      <h1>{{ $t('survey.thanks') }}</h1>
      <Button class="mt-2" @click="leave">{{ $t('button.login') }}</Button>
    </div>
  </section>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import Button from '@/components/atoms/Button.vue'
import { clearPendingSurvey, pendingSurvey, surveyUrl } from '@/utils/survey'

const router = useRouter()

/**
 * Read once: the request is cleared as soon as the chain is over, and the
 * iframe must not be reloaded when that happens.
 */
const survey = ref(pendingSurvey())
const url = computed(() => (survey.value ? surveyUrl(survey.value) : ''))
const done = ref(false)

/**
 * The chainer posts its aggregated answers to its embedder when the operator
 * presses Finish, and downloads them as a JSON file exactly as it does when
 * opened standalone. Nothing is sent to the backend - the file is the
 * deliverable, like the session trace export.
 */
function onMessage(event: MessageEvent) {
  if (event.origin !== window.location.origin) return
  if (!event.data?.success || !event.data.allResults) return
  done.value = true
  clearPendingSurvey()
}

/** Leave the questionnaire, taken or skipped, and drop the pending request. */
function leave() {
  clearPendingSurvey()
  router.push({ name: 'login' })
}

onMounted(() => window.addEventListener('message', onMessage))
onBeforeUnmount(() => window.removeEventListener('message', onMessage))
</script>
<style scoped lang="scss">
.survey {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
  height: 100%;

  header {
    text-align: center;
  }

  iframe {
    flex: 1;
    width: 100%;
    border: none;
    border-radius: var(--radius-medium);
    background: var(--color-background);
  }

  .cab-btn {
    align-self: center;
  }
}
</style>
