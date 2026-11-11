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

describe('Railway page', () => {
  it("shows today's page with the seed card and context", () => {
    login()
    // seed.py posts the card "Signalstörung" and one context
    cy.contains('Signalstörung', { timeout: 20000 }).should('be.visible')
    cy.screenshot('00-baseline', { capture: 'viewport' })
  })

  it('is German in a German browser', () => {
    login('de-DE')
    cy.contains('h1', 'Zeitachse', { timeout: 20000 }).should('be.visible')
    cy.contains('Signalstörung').click()
    cy.contains('Empfehlung anfordern').should('be.visible')
    cy.screenshot('03-german', { capture: 'viewport' })
  })
})
