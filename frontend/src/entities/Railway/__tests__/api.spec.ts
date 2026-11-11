import { beforeEach, describe, expect, it, vi } from 'vitest'

const post = vi.fn()
vi.mock('@/plugins/http', () => ({ default: { post: (...args: unknown[]) => post(...args) } }))

describe('applyRecommendation', () => {
  beforeEach(() => {
    post.mockReset()
    vi.stubEnv('VITE_RAILWAY_SIMU', '/railway-simu')
  })

  it("sends a simulator decision to the simulator's apply route", async () => {
    const { applyRecommendation } = await import('../api')
    const action = { scenario_id: 'scenario3', decision_index: 0, option_index: 1, event_id: 'ev' }
    await applyRecommendation(action)
    expect(post).toHaveBeenCalledWith('/railway-simu/api/v1/recommendations', action)
  })

  it('keeps /transport_plan for catalog recommendations', async () => {
    const { applyRecommendation } = await import('../api')
    await applyRecommendation({ simulation_name: 'x', targets_list: [] })
    expect(post).toHaveBeenCalledWith('/railway-simu/transport_plan', {
      simulation_name: 'x',
      targets_list: []
    })
  })
})
