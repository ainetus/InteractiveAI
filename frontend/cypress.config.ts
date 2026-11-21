import coverage from '@cypress/code-coverage/task'
import { defineConfig } from 'cypress'

export default defineConfig({
  e2e: {
    specPattern: 'cypress/e2e/**/*.{cy,spec}.{js,jsx,ts,tsx}',
    baseUrl: 'http://localhost:4173',
    chromeWebSecurity: false,
    // screenshots and a video of every run (gitignored), for the visual checks of the Railway plan
    video: true,
    setupNodeEvents(on, config) {
      coverage(on, config)
      // headless windows default to 1280x720 and cap the viewport of the screenshots
      on('before:browser:launch', (browser, launchOptions) => {
        if (browser.name === 'electron') {
          launchOptions.preferences.width = 1600
          launchOptions.preferences.height = 900
        } else if (browser.family === 'chromium') {
          launchOptions.args.push('--window-size=1600,900')
        }
        return launchOptions
      })

      return config
    }
  }
})
