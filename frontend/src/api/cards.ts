import http from '@/plugins/http'
import i18n from '@/plugins/i18n'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import type { Card, CardEvent } from '@/types/cards'
import { handleSessionExpired } from '@/utils/session'

/** Every open card stream, so `unsubscribe` closes all of them and not just the last one opened. */
const controllers = new Set<AbortController>()

const { t } = i18n.global

/**
 * How a card stream ended - the caller reconnects only on `closed` and `error`.
 *  - `closed`: the server or the network ended the stream
 *  - `error`: it could not be read (network failure mid-stream)
 *  - `aborted`: we closed it (`unsubscribe`)
 *  - `replaced`: the server handed it to a newer connection of the same user
 *  - `unauthorized`: the session is gone, already handled
 */
export type StreamEnd = 'closed' | 'error' | 'aborted' | 'replaced' | 'unauthorized'

export async function subscribe(
  config: {
    clientId: string
    rangeEnd?: string
    rangeStart?: string
    notification?: 'true' | 'false'
  },
  handler: (card: CardEvent) => void,
  retried = false
): Promise<StreamEnd> {
  const authStore = useAuthStore()
  const appStore = useAppStore()
  const controller = new AbortController()
  controllers.add(controller)
  try {
    const response = await fetch(
      import.meta.env.VITE_API +
        '/cards/cardSubscription?' +
        new URLSearchParams({
          ...config,
          version: 'SNAPSHOT'
        }),
      {
        headers: {
          Authorization: `Bearer ${authStore.token?.access_token}`
        },
        method: 'GET',
        signal: controller.signal
      }
    )
    // This request bypasses the axios interceptors, so the token dance lives here
    if (response.status === 401) {
      controllers.delete(controller)
      if (!retried && (await authStore.refresh())) return subscribe(config, handler, true)
      appStore.status.notifications.state = 'OFFLINE'
      handleSessionExpired()
      return 'unauthorized'
    }
    if (!response.ok || !response.body) return 'error'

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    // A network chunk ends wherever it ends - a card is often split over
    // several, so the unfinished last line is kept for the next one rather than
    // parsed (and dropped) on its own.
    let pending = ''
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      const lines = (pending + decoder.decode(value, { stream: true })).split('\n')
      pending = lines.pop() ?? ''
      for (const line of lines) {
        const payload = line.endsWith('\r') ? line.slice(0, -1) : line
        if (payload.slice(0, 5) !== 'data:') continue
        const data = payload.slice(5)
        switch (data) {
          case 'INIT':
          case 'RELOAD':
          case 'BUSINESS_CONFIG_CHANGE':
          case 'USER_CONFIG_CHANGE':
            break
          case 'HEARTBEAT':
            appStore.status.notifications.state = 'ONLINE'
            appStore.status.notifications.last = Date.now()
            break
          case 'DISCONNECT_USER_DUE_TO_NEW_CONNECTION':
            appStore.status.notifications.state = 'OFFLINE'
            controller.abort()
            appStore.addModal({
              data: t(`modal.error.DISCONNECT_USER_DUE_TO_NEW_CONNECTION`),
              type: 'info'
            })
            return 'replaced'
          default:
            try {
              handler(JSON.parse(data) as CardEvent)
            } catch (error) {
              console.warn('Unreadable card event, skipped:', error, data.slice(0, 200))
            }
        }
      }
    }
    return 'closed'
  } catch (error) {
    if (controller.signal.aborted) return 'aborted'
    console.warn('Card stream failed:', error)
    return 'error'
  } finally {
    controllers.delete(controller)
  }
}

export function isSubscriptionActive() {
  return http.get<boolean>('/cards/willNewSubscriptionDisconnectAnExistingSubscription')
}

export function get(id: Card['id']) {
  return http.get<{ card: Card }>(`/cards/cards/${id}`)
}

export function update(card: any) {
  return http.post<Card>(`/cab_event/api/v1/events`, card)
}

export function remove(id: Card['id']) {
  return http.delete<null>(`/cardspub/cards/${id}`)
}

/**
 * Deletes the event *and* its card (the event-service drops `cabProcess.{uid}`
 * from the card publication service on its way out).
 *
 * @param silent suppress the generic error modal - used by bulk deletions that
 *   report once instead of one popup per card
 */
export function removeEvent(uid: Card['processInstanceId'], silent = false) {
  return http.delete<null>(`/cab_event/api/v1/event/${uid}`, { _silent: silent })
}

export function acknowledge(card: Card) {
  return http.post<null>(`/cardspub/cards/userAcknowledgement/${card.uid}`, card.entityRecipients)
}

export function unsubscribe() {
  for (const controller of controllers) controller.abort()
}
