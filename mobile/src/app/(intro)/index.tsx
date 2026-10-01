import { Redirect } from 'expo-router';

/**
 * The intro starts on the Adapty flow (placement `onb_main`); that screen
 * falls back to the native welcome → quiz screens when no flow is available.
 */
export default function IntroIndex() {
  return <Redirect href="/(intro)/flow" />;
}
