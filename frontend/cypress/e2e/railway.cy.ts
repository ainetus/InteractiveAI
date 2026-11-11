// The Railway page on the dev stack (usecases_examples/Railway/devstack) or any deployment:
// CYPRESS_BASE_URL=http://localhost:3200, participant login from CYPRESS_USER / CYPRESS_PASSWORD
// (the dev gateway accepts any). Each step of docs/plans/railway-use-case.md adds its named shots.
// Every test starts from a clean feed and posts or starts what it shows.

const user = Cypress.env('USER') ?? 'railway_user'
const password = Cypress.env('PASSWORD') ?? 'test'

// Log in as the participant; `language` stands for the browser's language (Q7: the Railway page is
// German in a German browser).
function login(language?: string) {
  cy.viewport(1600, 900)
  cy.visit('/login', {
    onBeforeLoad(win) {
      if (language) Object.defineProperty(win.navigator, 'language', { value: language })
    }
  })
  cy.get('input[type="text"]').type(user)
  cy.get('input[type="password"]').type(password, { log: false })
  cy.get('button[type="submit"]').click()
  cy.location('pathname').should('eq', '/cab/Railway')
  // the consent question for cognitive data opens on every login
  cy.contains('button', /^(No|Nein|Non)$/, { timeout: 10000 }).click()
}

// No running session and no cards: DELETE /cardspub/cards is the dev gateway's stand-in for
// resources/deleteAllCards.sh.
function reset() {
  cy.request({ method: 'POST', url: '/railway-simu/api/v1/session/stop', failOnStatusCode: false })
  cy.request({ method: 'DELETE', url: '/cardspub/cards', failOnStatusCode: false })
}

// A card and a context in today's schema (GPS trains, no track network), as devstack/seed.py posts
// them. Posted after login: the page ignores a context that was already there at its first poll
// (stores/services.ts).
function postTodayEventAndContext() {
  const now = new Date().toISOString()
  cy.request('POST', '/cab_event/api/v1/events', {
    use_case: 'Railway',
    criticality: 'HIGH',
    title: 'Signalstörung',
    description: "Seed event of the dev stack, in today's Railway schema.",
    start_date: now,
    data: {
      event_type: 'INFRASTRUCTURE',
      id_train: 'AB001',
      agent_id: '0',
      id_event: `cypress-${Date.now()}`,
      delay: 15
    }
  })
  cy.request('POST', '/cabcontext/api/v1/contexts', {
    use_case: 'Railway',
    date: now,
    data: {
      trains: [
        {
          id_train: 'AB001',
          nb_passengers_onboard: 468,
          latitude: 46.58,
          longitude: 0.33,
          failure: true
        }
      ]
    }
  })
}

// Start a single run on the simulator through /railway-simu/, as the start dialog will (S12); until
// then the spec starts sessions itself. After login, for the same reason as above.
function startRun(scenarioId: string, mode: 'recommendation' | 'colearning') {
  cy.request('POST', '/railway-simu/api/v1/session', {
    session_id: `cypress-${Date.now()}`,
    kind: 'single',
    scenario_id: scenarioId,
    mode
  })
  cy.request('POST', '/railway-simu/api/v1/session/next')
}

// Wait until the latest context says the run is in `state`.
function waitForRun(state: string, tries = 120) {
  cy.request('/cabcontext/api/v1/contexts').then(({ body }) => {
    const context = Array.isArray(body) ? body[0] : body
    if (context?.data?.scenario?.state === state) return
    if (tries <= 0) throw new Error(`the run never reached ${state}`)
    // pacing the poll of the context, not waiting for the page
    // eslint-disable-next-line cypress/no-unnecessary-waiting
    cy.wait(500, { log: false })
    waitForRun(state, tries - 1)
  })
}

describe('Railway page', () => {
  beforeEach(reset)

  it("shows today's page with a card and a context in today's schema", () => {
    login()
    postTodayEventAndContext()
    // contexts without a track network keep the geographic map
    cy.get('.leaflet-container', { timeout: 20000 }).should('be.visible')
    cy.get('.leaflet-tile-loaded', { timeout: 20000 }).should('have.length.greaterThan', 3)
    cy.contains('Signalstörung', { timeout: 20000 }).should('be.visible')
    cy.screenshot('00-baseline', { capture: 'viewport' })
  })

  it('shows the cards the simulator sends', () => {
    login()
    startRun('scenario2', 'recommendation')
    // scenario 2: the door fault at step 3, the conflict that carries the decision at step 15
    cy.contains('Türstörung — S 17', { timeout: 30000 }).should('be.visible')
    cy.contains('Dispositionskonflikt — Entscheidung erforderlich', { timeout: 30000 }).should(
      'be.visible'
    )
    cy.screenshot('01-feed', { capture: 'viewport' })
  })

  it("shows a decision's recommendations from the Recommendation Service", () => {
    login()
    startRun('scenario3', 'recommendation')
    // scenario 3 pauses at step 16 with the conflict card that carries the decision
    waitForRun('paused_for_decision')
    cy.get('.railway-network', { timeout: 20000 }).should('be.visible')
    cy.contains('Dispositionskonflikt — G 3 fährt langsam', { timeout: 30000 }).click()
    cy.contains('button', 'Get recommendation').click()
    cy.contains('IC 3 + IR 35 folgen G 3 mit halber Geschwindigkeit', { timeout: 20000 }).should(
      'be.visible'
    )
    cy.contains('G 3 weicht aus — IC 3 + IR 35 überholen').should('be.visible')
    cy.screenshot('02-recommendations', { capture: 'viewport' })
  })

  it('is German in a German browser', () => {
    login('de-DE')
    postTodayEventAndContext()
    cy.contains('h1', 'Zeitachse', { timeout: 20000 }).should('be.visible')
    cy.contains('Signalstörung', { timeout: 20000 }).click()
    cy.contains('Empfehlung anfordern').should('be.visible')
    cy.screenshot('03-german', { capture: 'viewport' })
  })

  it("draws the scenario's track network and trains", () => {
    login()
    startRun('scenario1', 'recommendation')
    cy.get('.railway-network', { timeout: 20000 }).should('be.visible')
    // S 17 departs at step 1, S 18 at step 22; the context of every N steps brings them on the map
    cy.get('.railway-network [data-train="Train_1"]', { timeout: 40000 }).should('exist')
    cy.contains('.railway-network text', 'Station 1').should('exist')
    cy.screenshot('04-map', { capture: 'viewport' })
  })

  it('draws the time-distance diagram from the history', () => {
    login()
    startRun('scenario1', 'recommendation')
    // scenario 1 pauses at step 40: the trains' lines up to the decision
    waitForRun('paused_for_decision')
    cy.get('.railway-network', { timeout: 20000 }).should('be.visible')
    cy.contains('.cab-tab', 'Time-distance diagram').click()
    cy.get('.railway-zwl [data-train="Train_0"] .actual', { timeout: 20000 }).should('exist')
    cy.contains('.railway-zwl .now text', 'Step 40').should('exist')
    cy.screenshot('05-zwl', { capture: 'viewport' })
  })
})
