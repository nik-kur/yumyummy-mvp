/**
 * Dark photo screen shared by B3 (19) and the offer (20): a 390 × 694 photo
 * pinned to the top (scaled to the screen width), a calorie badge on it, a
 * fade into ink and a bottom block over the fade.
 *
 * The fade follows the bottom block, not fixed numbers: on a short phone the
 * block starts higher, so the fade starts higher too and the headline never
 * sits on a bright part of the photo. On the 390 × 844 artboard it lands
 * exactly where drawn. The fade always ends on the photo and solid ink runs
 * a little past its bottom edge: an exposed edge showed as a thin light line
 * across the screen (phone test, build 64).
 */
import { useState, type ReactNode } from 'react';
import { PixelRatio, StyleSheet, useWindowDimensions, View } from 'react-native';
import { Image } from 'expo-image';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { C } from '@/onb/theme';

import type { BadgeSpec } from './copy';
import { InkFade, PhotoBadge } from './PwParts';

const ART_W = 390;
const PHOTO_H = 694;

interface Props {
  photo: number;
  badge: BadgeSpec | null;
  /**
   * Artboard fade: starts `fadeTop`, and sits `above` / `below` the block top
   * as drawn; `atBlock` = how dark it already is at the block top (default:
   * a straight ramp).
   */
  fade: { top: number; above: number; below: number; atBlock?: number };
  /** Accessible description of the photo. */
  label: string;
  /** Over the photo, e.g. the offer's close button. */
  overlay?: ReactNode;
  children: ReactNode;
}

export function PhotoStage({ photo, badge, fade, label, overlay, children }: Props) {
  const { width: W, height: H } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const k = W / ART_W;
  const photoH = PixelRatio.roundToNearestPixel(PHOTO_H * k);
  const [blockH, setBlockH] = useState(0);
  const [badgeH, setBadgeH] = useState(0);
  const blockTop = H - blockH;
  // On a short phone a low badge (b3_wide) would sit on the headline: lift it
  // above the block, and drop it if there is no room left under the status bar.
  const badgeTop = badge ? Math.min(badge.top * k, blockTop - badgeH - 12) : 0;
  const badgeFits = badgeTop >= insets.top + 4;
  const fadeEnd = PixelRatio.roundToNearestPixel(Math.min(photoH, Math.max(blockTop + fade.below, 80)));
  const fadeTop = PixelRatio.roundToNearestPixel(Math.min(fade.top * k, blockTop - fade.above, fadeEnd - 80));
  // Where the block starts inside the fade, for an eased ramp.
  const mid =
    fade.atBlock !== undefined && blockTop > fadeTop && blockTop < fadeEnd
      ? { at: (blockTop - fadeTop) / (fadeEnd - fadeTop), opacity: fade.atBlock }
      : undefined;
  return (
    <View style={s.screen}>
      <Image
        source={photo}
        style={{ position: 'absolute', left: 0, top: 0, width: W, height: photoH }}
        contentFit="cover"
        contentPosition="top"
        accessibilityLabel={label}
      />
      <InkFade top={fadeTop} height={fadeEnd - fadeTop} mid={mid} />
      <View style={[s.solid, { top: fadeEnd - 1, height: photoH - fadeEnd + 3 }]} />
      {badge ? (
        <View
          onLayout={(e) => setBadgeH(e.nativeEvent.layout.height)}
          style={{
            position: 'absolute',
            top: badgeTop,
            width: badge.width,
            opacity: blockH > 0 && !badgeFits ? 0 : 1,
            ...(badge.left !== undefined ? { left: badge.left * k } : { right: (badge.right ?? 0) * k }),
          }}
        >
          <PhotoBadge title={badge.title} kcal={badge.kcal} source={badge.source} />
        </View>
      ) : null}
      {overlay}
      <View
        style={[s.block, { paddingBottom: Math.max(insets.bottom - 4, 16) }]}
        onLayout={(e) => setBlockH(e.nativeEvent.layout.height)}
      >
        {children}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.ink, overflow: 'hidden' },
  solid: { position: 'absolute', left: 0, right: 0, backgroundColor: C.ink },
  block: { position: 'absolute', left: 0, right: 0, bottom: 0, paddingHorizontal: 24 },
});
