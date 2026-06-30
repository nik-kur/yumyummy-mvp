/** @type {import('@bacons/apple-targets/app.plugin').ConfigFunction} */
module.exports = (config) => ({
  type: 'widget',
  name: 'YumYummyWidget',
  // iOS 17 lets the quick-log buttons work in small + medium widgets via App Intents.
  deploymentTarget: '17.0',
  colors: {
    // Tint for buttons in the widget gallery / edit mode.
    $accent: '#B85A3A',
    $widgetBackground: '#FFFDF9',
  },
  entitlements: {
    // Mirror the App Group from app.json so the app and widget share storage.
    'com.apple.security.application-groups':
      config.ios.entitlements['com.apple.security.application-groups'],
  },
});
