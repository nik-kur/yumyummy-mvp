// Metro config wrapped by Sentry so bundles + sourcemaps get matching Debug IDs.
// Without this, uploaded sourcemaps don't line up with Hermes stack traces and
// crashes stay minified. `getSentryExpoConfig` is a drop-in for Expo's
// `getDefaultConfig` (it calls it internally, then adds the Sentry serializer).
const { getSentryExpoConfig } = require('@sentry/react-native/metro');

const config = getSentryExpoConfig(__dirname);

module.exports = config;
