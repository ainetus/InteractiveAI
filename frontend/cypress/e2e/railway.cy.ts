// The Railway page on the dev stack (usecases_examples/Railway/devstack) or any deployment:
// CYPRESS_BASE_URL=http://localhost:3200, participant login from CYPRESS_USER / CYPRESS_PASSWORD
// (the dev gateway accepts any). Each step of docs/plans/railway-use-case.md adds its named shots.
// Every test starts from a clean feed and posts what it shows, or starts it in the start dialog.

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

// A deployment without the simulator: GET /api/v1/scenarios fails, so the page shows no start
// dialog and stays as today. Before login.
function withoutSimulator() {
  cy.intercept('GET', '/railway-simu/api/v1/scenarios', { statusCode: 404, body: {} })
}

// Start a single run in the start dialog (the Szenario-Loader, F21); it starts at once, without
// an introduction (Q13 d). After login.
function startRun(scenarioId: string, mode: 'recommendation' | 'colearning') {
  cy.get('.railway-loader[data-view="start"]', { timeout: 20000 }).within(() => {
    cy.get('select[name="scenario"]').select(scenarioId)
    cy.get('select[name="mode"]').select(mode)
    cy.get('[data-start="single"]').click()
  })
  cy.get('.railway-loader', { timeout: 20000 }).should('not.exist')
}

// Wait until the latest context's data passes `check`.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function waitForContext(what: string, check: (data: any) => boolean, tries = 120) {
  cy.request('/cabcontext/api/v1/contexts').then(({ body }) => {
    const context = Array.isArray(body) ? body[0] : body
    if (context?.data && check(context.data)) return
    if (tries <= 0) throw new Error(`the context never showed ${what}`)
    // pacing the poll of the context, not waiting for the page
    // eslint-disable-next-line cypress/no-unnecessary-waiting
    cy.wait(500, { log: false })
    waitForContext(what, check, tries - 1)
  })
}

// Wait until the latest context says the run is in `state`.
function waitForRun(state: string) {
  waitForContext(`the run ${state}`, (data) => data.scenario?.state === state)
}

describe('Railway page', () => {
  beforeEach(reset)

  it("shows today's page with a card and a context in today's schema", () => {
    withoutSimulator()
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
    withoutSimulator()
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

  it('shows the step and the open decision above the drawing', () => {
    login('de-DE')
    startRun('scenario3', 'colearning')
    waitForRun('paused_for_decision')
    cy.contains('.railway-status .step', 'Schritt 16', { timeout: 20000 }).should('be.visible')
    cy.contains('.railway-status', 'Entscheidung erforderlich – bitte Ereigniskarte öffnen').should(
      'be.visible'
    )
    cy.contains('button', 'Zugtabelle').click()
    cy.contains('.railway-trains', 'unterwegs').should('be.visible')
    cy.screenshot('06-status', { capture: 'viewport' })
  })

  it("applies one of a decision's options in Empfehlungsmodus", () => {
    login('de-DE')
    startRun('scenario3', 'recommendation')
    waitForRun('paused_for_decision')
    cy.contains('Dispositionskonflikt — G 3 fährt langsam', { timeout: 30000 }).click()
    cy.contains('button', 'Empfehlung anfordern').click()
    cy.contains('.railway-decision .badge', 'Entscheidung erforderlich', { timeout: 20000 }).should(
      'be.visible'
    )
    cy.contains('.cab-recommendation', 'G 3 weicht aus — IC 3 + IR 35 überholen').click()
    cy.contains('.railway-kpis td', 'Lokale Verspätung').should('be.visible')
    cy.screenshot('07-decision-recommendation', { capture: 'viewport' })

    // "Anwenden", confirmed: the choice goes to the simulator through /railway-simu/, which
    // resumes the run (F20)
    cy.contains('button', 'Anwenden').click()
    cy.contains('button', 'Ja').click()
    cy.contains('Lösung angewendet.', { timeout: 20000 }).should('be.visible')
    waitForContext('the applied decision', (data) => data.decisions?.length === 1)
    waitForRun('running')
    cy.contains('.railway-status', 'Entscheidung erforderlich', { timeout: 20000 }).should(
      'not.exist'
    )
    // the trains move on past the decision's step 16: their lines in the ZWL diagram go on
    cy.contains('.railway-status .step', /Schritt (1[7-9]|[2-9]\d)/, { timeout: 20000 }).should(
      'be.visible'
    )
    cy.contains('.cab-tab', 'ZWL Diagramm').click()
    cy.get('.railway-zwl [data-train="Train_0"] .actual').should('exist')
    cy.screenshot('09-after-apply', { capture: 'viewport' })
  })

  it('chooses a train, then an action, in Ko-Lernen', () => {
    login('de-DE')
    startRun('scenario2', 'colearning')
    waitForRun('paused_for_decision')
    cy.contains('Dispositionskonflikt — Entscheidung erforderlich', { timeout: 30000 }).click()
    cy.contains('button', 'Empfehlung anfordern').click()
    cy.contains('.railway-colearning button', 'S 17-2', { timeout: 20000 }).click()
    // umleiten is not offered for S 17-2; warten is offered but not feasible and says why
    cy.contains('.railway-colearning button', 'Umleiten').should('be.disabled')
    cy.contains('.railway-colearning button', 'Warten').click()
    cy.get('.railway-colearning .reason').should('be.visible')
    cy.contains('.railway-colearning button', 'Lösung vorschlagen').should('be.disabled')
    cy.contains('.railway-colearning button', 'Vorfahrt').click()
    cy.contains('.railway-colearning h3', 'Vorschau: Auswirkungen').should('be.visible')
    cy.screenshot('08-decision-colearning', { capture: 'viewport' })

    // "Lösung vorschlagen" applies at once, without a confirmation (Q8 a)
    cy.contains('.railway-colearning button', 'Lösung vorschlagen').click()
    cy.contains('Lösung angewendet.', { timeout: 20000 }).should('be.visible')
    waitForContext('the applied decision', (data) => data.decisions?.length === 1)
  })

  it('leaves the start dialog for the geographic map of an external simulation', () => {
    login('de-DE')
    cy.get('.railway-loader[data-view="start"]', { timeout: 20000 }).should('be.visible')
    cy.get('[data-standalone]').click()
    cy.get('.railway-loader').should('not.exist')
    cy.contains('.railway-progress', 'Standalone-Modus').should('be.visible')
    // the geographic map, although the latest context may be a scenario run's grid (Q31)
    cy.get('.leaflet-container').should('be.visible')
    postTodayEventAndContext()
    cy.get('.leaflet-marker-icon', { timeout: 20000 }).should('exist')
    // the map tiles load after the marker; the shot waits for them, not for the app
    // eslint-disable-next-line cypress/no-unnecessary-waiting
    cy.wait(2000)
    cy.screenshot('15-standalone', { capture: 'viewport' })

    cy.contains('.railway-progress button', 'Szenario-Loader').click()
    cy.get('.railway-loader[data-view="start"]').should('be.visible')
  })

  it('ends the current scenario and moves on in the Experiment', () => {
    login('de-DE')
    cy.get('[data-start="experiment"]', { timeout: 20000 }).click()
    cy.contains('.railway-loader h1', 'Run 1/6', { timeout: 20000 }).should('be.visible')
    cy.contains('.railway-loader button', 'Weiter').click()
    cy.get('.railway-loader', { timeout: 20000 }).should('not.exist')
    // the Experiment's bar: end the run, or the whole Experiment (finding 6)
    cy.contains('.railway-progress [data-stop]', 'Experiment beenden').should('be.visible')
    cy.get('.railway-progress [data-end-run]', { timeout: 20000 }).should('be.visible')
    waitForContext('run 1 moving', (data) => (data.scenario?.step ?? 0) >= 8)
    cy.screenshot('17-end-run', { capture: 'viewport' })

    cy.get('.railway-progress [data-end-run]').click()
    cy.contains('.railway-loader h1', 'Run 2/6', { timeout: 20000 }).should('be.visible')
    cy.contains('.railway-loader button', 'Experiment beenden').should('be.visible')
  })

  it('plays the Experiment from the start dialog to the end screen and the reflection', () => {
    login('de-DE')
    cy.get('.railway-loader[data-view="start"]', { timeout: 20000 }).should('be.visible')
    cy.get('[data-start="experiment"]').click()
    // run 1's introduction (F22), its scenario drawn from the trace session id
    cy.contains('.railway-loader h1', 'Szenario-Einführung — Run 1/6', { timeout: 20000 }).should(
      'be.visible'
    )
    cy.get('.railway-loader .introduction').should('not.be.empty')
    cy.screenshot('10-intro', { capture: 'viewport' })

    cy.contains('.railway-loader button', 'Weiter').click()
    cy.get('.railway-loader', { timeout: 20000 }).should('not.exist')
    cy.contains('.railway-progress', 'Experiment 1/6').should('be.visible')

    // the end screen (F26) without playing six runs: the latest context is rewritten into the
    // last run's, complete, with the session ended, under a new id so the page takes it
    cy.intercept('GET', '/cabcontext/api/v1/contexts*', (req) => {
      req.continue((res) => {
        const context = Array.isArray(res.body) ? res.body[0] : res.body
        const data = context?.data
        if (!data?.session) return
        context.id_context = `${context.id_context}-end`
        data.session.scenario_position = data.session.scenario_order.length - 1
        data.session.ended_at = new Date().toISOString()
        data.scenario.state = 'complete'
      })
    })
    cy.contains('.railway-loader h1', 'Experiment abgeschlossen', { timeout: 30000 }).should(
      'be.visible'
    )
    cy.contains('.railway-loader', 'Bitte melden Sie sich jetzt oben rechts ab').should(
      'be.visible'
    )
    cy.screenshot('12-end', { capture: 'viewport' })

    // the logout opens the post-logout survey with Railway's chain (Q5 d)
    cy.get('button[aria-label="Anmelden"]').click()
    cy.contains('button', /^(Ja|Yes|Oui)$/).click()
    cy.location('pathname', { timeout: 20000 }).should('eq', '/survey')
    cy.get('iframe')
      .its('0.contentDocument.body')
      .should('not.be.empty')
      .then(cy.wrap)
      .within(() => {
        cy.contains('button', 'Starten', { timeout: 20000 }).click()
        cy.get('#surveyFrame')
          .its('0.contentDocument.body')
          .should('contain.text', 'Auf welche Logik habe ich mich gestützt?')
      })
    cy.get('iframe').should('be.visible')
    // the page fades in after the route change; the shot waits for it, not for the app
    // eslint-disable-next-line cypress/no-unnecessary-waiting
    cy.wait(1500)
    cy.screenshot('11-reflection', { capture: 'viewport' })
  })

  it('plays a scenario in Empfehlungsmodus from login to its end', () => {
    login('de-DE')
    startRun('scenario2', 'recommendation')
    waitForRun('paused_for_decision')
    cy.contains('Dispositionskonflikt — Entscheidung erforderlich', { timeout: 30000 }).click()
    cy.contains('button', 'Empfehlung anfordern').click()
    cy.get('.cab-recommendation', { timeout: 20000 }).first().click()
    cy.contains('button', 'Anwenden').click()
    cy.contains('button', 'Ja').click()
    cy.contains('Lösung angewendet.', { timeout: 20000 }).should('be.visible')
    waitForRun('complete')
    cy.contains('.railway-progress', 'Einzelner Lauf · Szenario 2', { timeout: 20000 }).should(
      'contain.text',
      'abgeschlossen'
    )
    cy.contains('.railway-progress button', 'Neue Sitzung').click()
    cy.get('.railway-loader[data-view="start"]').should('be.visible')
  })

  it('plays a scenario in Ko-Lernen from login to its end, as the reference screenshot', () => {
    login('de-DE')
    startRun('scenario3', 'colearning')
    waitForRun('paused_for_decision')
    cy.contains('Dispositionskonflikt — G 3 fährt langsam', { timeout: 30000 }).click()
    cy.contains('button', 'Empfehlung anfordern').click()
    cy.contains('.railway-colearning button', 'IC 3 dann IR 35', { timeout: 20000 }).should(
      'be.visible'
    )
    // the state of docs/plans/railway-use-case/railway_sim.png: scenario 3 in Ko-Lernen at step 16
    cy.screenshot('14-compare', { capture: 'viewport' })

    cy.contains('.railway-colearning button', 'IC 3 dann IR 35').click()
    cy.contains('.railway-colearning button', 'Vorfahrt').click()
    cy.contains('.railway-colearning button', 'Lösung vorschlagen').click()
    cy.contains('Lösung angewendet.', { timeout: 20000 }).should('be.visible')
    waitForRun('complete')
    cy.contains('.railway-progress', 'Ko-Lernen', { timeout: 20000 }).should(
      'contain.text',
      'abgeschlossen'
    )
  })

  it('draws the line view from the link map', () => {
    login()
    startRun('scenario3', 'recommendation')
    // scenario 3 at its decision: G 3 on the main line, IC 3 and IR 35 behind it
    waitForRun('paused_for_decision')
    cy.get('.railway-network', { timeout: 20000 }).should('be.visible')
    cy.contains('.cab-tab', 'Line view').click()
    cy.get('.railway-linkmap [data-train="Train_0"]', { timeout: 20000 }).should('exist')
    cy.screenshot('13-link-map', { capture: 'viewport' })
  })
})
