// The Railway page on the dev stack (usecases_examples/Railway/devstack) or any deployment:
// CYPRESS_BASE_URL=http://localhost:3200, participant login from CYPRESS_USER / CYPRESS_PASSWORD
// (the dev gateway accepts any). Each step of docs/plans/railway-use-case.md adds its named shots.

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

// Start a single run on the simulator through the gateway's /railway-simu/, as the start dialog
// will (S12); until then the spec starts sessions itself. Ends any session left by an earlier test.
function startRun(scenarioId: string, mode: 'recommendation' | 'colearning') {
  cy.request({ method: 'POST', url: '/railway-simu/api/v1/session/stop', failOnStatusCode: false })
  cy.request('POST', '/railway-simu/api/v1/session', {
    session_id: `cypress-${Date.now()}`,
    kind: 'single',
    scenario_id: scenarioId,
    mode
  })
  cy.request('POST', '/railway-simu/api/v1/session/next')
}

describe('Railway page', () => {
  it("shows today's page with the seed card and context", () => {
    login()
    // seed.py posts the card "Signalstörung" and one context
    cy.contains('Signalstörung', { timeout: 20000 }).should('be.visible')
    cy.screenshot('00-baseline', { capture: 'viewport' })
  })

  it('shows the cards the simulator sends', () => {
    startRun('scenario2', 'recommendation')
    login()
    // scenario 2: the door fault at step 3, the conflict that carries the decision at step 15
    cy.contains('Türstörung — S 17', { timeout: 30000 }).should('be.visible')
    cy.contains('Dispositionskonflikt — Entscheidung erforderlich', { timeout: 30000 }).should(
      'be.visible'
    )
    cy.screenshot('01-feed', { capture: 'viewport' })
    cy.request('POST', '/railway-simu/api/v1/session/stop')
  })

  it("shows a decision's recommendations from the Recommendation Service", () => {
    // after login: the page ignores a context that was there before its first poll (stores/services.ts)
    login()
    startRun('scenario3', 'recommendation')
    // scenario 3 pauses at step 16 with the conflict card that carries the decision
    cy.contains('Dispositionskonflikt — G 3 fährt langsam', { timeout: 30000 }).click()
    cy.contains('button', 'Get recommendation').click()
    cy.contains('IC 3 + IR 35 folgen G 3 mit halber Geschwindigkeit', { timeout: 20000 }).should(
      'be.visible'
    )
    cy.contains('G 3 weicht aus — IC 3 + IR 35 überholen').should('be.visible')
    cy.screenshot('02-recommendations', { capture: 'viewport' })
    cy.request('POST', '/railway-simu/api/v1/session/stop')
  })

  it('is German in a German browser', () => {
    login('de-DE')
    cy.contains('h1', 'Zeitachse', { timeout: 20000 }).should('be.visible')
    cy.contains('Signalstörung').click()
    cy.contains('Empfehlung anfordern').should('be.visible')
    cy.screenshot('03-german', { capture: 'viewport' })
  })
})
