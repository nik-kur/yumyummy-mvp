/**
 * V3 screen 4 — Where did you hear about us? (after Reflect, agreed 15 Oct).
 * The answer goes to PostHog and to the Adapty profile (`self_source`), so an
 * audience can key on it even when ad attribution is missing.
 */
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import Svg, { Circle, Defs, G, LinearGradient, Path, Rect, Stop } from 'react-native-svg';

import { setAdaptyCustomAttributes } from '@/billing/adapty';
import { ChoiceScreen, type Choice } from '@/components/onb/ChoiceScreen';
import { IMG } from '@/onb/assets';
import { useOnbScreen } from '@/onb/useOnbScreen';

type SourceKey =
  | 'podcast' | 'tv' | 'instagram' | 'tiktok' | 'facebook' | 'youtube'
  | 'doctor' | 'friends' | 'app_store' | 'other';

/** Brand marks as drawn on the canvas (30 pt tile, white plate, soft shadow). */
function Logo({ children, round }: { children: React.ReactNode; round?: boolean }) {
  return <View style={[s.tile, round && s.round]}>{children}</View>;
}

const INSTAGRAM = (
  <Logo>
    <Svg width={30} height={30} viewBox="0 0 36 36">
      <Defs>
        <LinearGradient id="yyig" x1="0" y1="1" x2="1" y2="0">
          <Stop offset="0" stopColor="#FEC053" />
          <Stop offset="0.35" stopColor="#F2203E" />
          <Stop offset="0.7" stopColor="#B729A8" />
          <Stop offset="1" stopColor="#5342D6" />
        </LinearGradient>
      </Defs>
      <Rect x={4} y={4} width={28} height={28} rx={8} fill="url(#yyig)" />
      <Rect x={10.5} y={10.5} width={15} height={15} rx={4.6} stroke="#FFFFFF" strokeWidth={2} fill="none" />
      <Circle cx={18} cy={18} r={3.6} stroke="#FFFFFF" strokeWidth={2} fill="none" />
      <Circle cx={22.6} cy={13.4} r={1.2} fill="#FFFFFF" />
    </Svg>
  </Logo>
);

const TIKTOK_PATHS = (stroke: string, dx: number) => (
  <G stroke={stroke} strokeWidth={2.6} strokeLinecap="round" fill="none" transform={`translate(${dx} ${dx})`}>
    <Path d="M19 10.5v11.3a3.6 3.6 0 1 1-3.6-3.6" />
    <Path d="M19 10.5c.6 2.6 2.4 4.1 4.8 4.3" />
  </G>
);

const TIKTOK = (
  <Logo>
    <Svg width={30} height={30} viewBox="0 0 36 36">
      <Rect x={4} y={4} width={28} height={28} rx={8} fill="#111111" />
      {TIKTOK_PATHS('#25F4EE', -1)}
      {TIKTOK_PATHS('#FE2C55', 1)}
      {TIKTOK_PATHS('#FFFFFF', 0)}
    </Svg>
  </Logo>
);

const FACEBOOK = (
  <Logo round>
    <Svg width={30} height={30} viewBox="0 0 36 36">
      <Circle cx={18} cy={18} r={14} fill="#1877F2" />
      <Path
        d="M19.6 32v-9.6h3.2l.5-3.8h-3.7v-2.4c0-1.1.3-1.8 1.9-1.8h2v-3.4c-.3 0-1.5-.1-2.9-.1-2.9 0-4.8 1.7-4.8 4.9v2.8h-3.2v3.8h3.2V32z"
        fill="#FFFFFF"
      />
    </Svg>
  </Logo>
);

const YOUTUBE = (
  <Logo>
    <Svg width={30} height={30} viewBox="0 0 36 36">
      <Rect x={4} y={8} width={28} height={20} rx={6} fill="#FF0000" />
      <Path d="M15.2 13.6v8.8l7.6-4.4z" fill="#FFFFFF" />
    </Svg>
  </Logo>
);

const APP_STORE = (
  <Logo>
    <Svg width={30} height={30} viewBox="0 0 36 36">
      <Defs>
        <LinearGradient id="yyas" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor="#1BC6FB" />
          <Stop offset="1" stopColor="#1F6BF2" />
        </LinearGradient>
      </Defs>
      <Rect x={4} y={4} width={28} height={28} rx={8} fill="url(#yyas)" />
      <G stroke="#FFFFFF" strokeWidth={2.2} strokeLinecap="round">
        <Path d="M12.4 24.2l7.2-12.4" />
        <Path d="M16.4 11.8l7.2 12.4" />
        <Path d="M10.8 20.6h14.4" />
      </G>
    </Svg>
  </Logo>
);

const OPTIONS: Choice<SourceKey>[] = [
  { key: 'podcast', label: 'Podcast', icon: IMG.src_podcast },
  { key: 'tv', label: 'TV', icon: IMG.src_tv },
  { key: 'instagram', label: 'Instagram', iconNode: INSTAGRAM },
  { key: 'tiktok', label: 'TikTok', iconNode: TIKTOK },
  { key: 'facebook', label: 'Facebook', iconNode: FACEBOOK },
  { key: 'youtube', label: 'YouTube', iconNode: YOUTUBE },
  { key: 'doctor', label: 'Doctor or dietitian', icon: IMG.src_doctor },
  { key: 'friends', label: 'Friend or family', icon: IMG.src_friends },
  { key: 'app_store', label: 'App Store', iconNode: APP_STORE },
  { key: 'other', label: 'Other', icon: IMG.misc_dots },
];

export default function SourceScreen() {
  const { intro, next, progress } = useOnbScreen('S4_source');
  const [source, setSource] = useState<SourceKey | null>((intro.source as SourceKey | null) ?? null);
  return (
    <ChoiceScreen
      progress={progress}
      title="Where did you hear about us?"
      options={OPTIONS}
      value={source}
      onChange={setSource}
      compact
      gap={6}
      iconSize={30}
      titleMarginTop={20}
      spacers={[1, 1]}
      onContinue={() => {
        if (!source) return;
        void setAdaptyCustomAttributes({ self_source: source });
        next({ source }, { source }, { onb_source: source });
      }}
    />
  );
}

const s = StyleSheet.create({
  tile: {
    width: 30,
    height: 30,
    borderRadius: 9,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#2A1C0E',
    shadowOpacity: 0.18,
    shadowRadius: 1.5,
    shadowOffset: { width: 0, height: 1 },
  },
  round: { borderRadius: 15 },
});
