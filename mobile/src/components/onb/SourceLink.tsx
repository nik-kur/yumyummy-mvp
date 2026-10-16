/** "Study · Journal, year ↗" link under a claim (opens the study in the in-app browser). */
import { Pressable, StyleSheet, Text, type StyleProp, type ViewStyle } from 'react-native';
import * as WebBrowser from 'expo-web-browser';
import Svg, { Path } from 'react-native-svg';

import { track } from '@/analytics/posthog';
import { C, F } from '@/onb/theme';

export function SourceLink({ label, url, style }: { label: string; url: string; style?: StyleProp<ViewStyle> }) {
  return (
    <Pressable
      style={[s.row, style]}
      hitSlop={8}
      onPress={() => {
        track('onboarding_source_opened', { url });
        void WebBrowser.openBrowserAsync(url).catch(() => {});
      }}
      accessibilityRole="link"
    >
      <Text style={s.text}>{label}</Text>
      <Svg width={12} height={12} viewBox="0 0 24 24" fill="none">
        <Path d="M15 3h6v6" stroke={C.info} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" />
        <Path d="M10 14 21 3" stroke={C.info} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" />
        <Path
          d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"
          stroke={C.info}
          strokeWidth={1.6}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </Svg>
    </Pressable>
  );
}

const s = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  text: { fontFamily: F.sans, fontSize: 13, lineHeight: 18, color: C.faint },
});
