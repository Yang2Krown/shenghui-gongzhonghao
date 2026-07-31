const { defineConfig } = require('cypress')

module.exports = defineConfig({
  e2e: {
    baseUrl: process.env.CYPRESS_BASE_URL || 'http://127.0.0.1:4173',
    specPattern: 'cypress/e2e/**/*.cy.{js,jsx}',
    supportFile: false,
    viewportWidth: 1536,
    viewportHeight: 900,
    video: false,
    screenshotOnRunFailure: true,
  },
})
