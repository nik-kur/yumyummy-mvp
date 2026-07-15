/**
 * YumYummy apple mascot — reuses weekly-recap mood art with light motion.
 */
import { useEffect } from 'react';
import { Image, StyleSheet, View, type ImageStyle, type StyleProp, type ViewStyle } from 'react-native';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
  Easing,
} from 'react-native-reanimated';

import { AppText } from './AppText';
import { colors } from '@/theme/tokens';
import { fonts } from '@/theme/typography';

// Transparent cutouts of the recap mood art (no baked-in background square).
const MOOD = {
  welcome: require('../../assets/mascot/mood_stellar_t.png'), // joyful jump
  thumbsUp: require('../../assets/mascot/mood_great_t.png'), // thumbs up
  celebrate: require('../../assets/mascot/mood_stellar_t.png'),
  hungry: require('../../assets/mascot/mood_hungry_t.png'), // bib + cutlery, waiting for a meal
} as const;

export type MascotVariant = keyof typeof MOOD;

interface MascotBadgeProps {
  variant?: MascotVariant;
  size?: number;
  /** Large serif label shown beside the mascot (fix / brand moments). */
  label?: string;
  style?: StyleProp<ViewStyle>;
  imageStyle?: StyleProp<ImageStyle>;
}

export function MascotBadge({
  variant = 'welcome',
  size = 72,
  label,
  style,
  imageStyle,
}: MascotBadgeProps) {
  const bounce = useSharedValue(0);
  const tilt = useSharedValue(0);

  useEffect(() => {
    bounce.value = withRepeat(
      withSequence(
        withTiming(-6, { duration: 700, easing: Easing.inOut(Easing.ease) }),
        withTiming(0, { duration: 700, easing: Easing.inOut(Easing.ease) }),
      ),
      -1,
      true,
    );
    if (variant === 'thumbsUp') {
      tilt.value = withRepeat(
        withSequence(
          withTiming(-4, { duration: 900, easing: Easing.inOut(Easing.ease) }),
          withTiming(4, { duration: 900, easing: Easing.inOut(Easing.ease) }),
        ),
        -1,
        true,
      );
    }
  }, [bounce, tilt, variant]);

  const animStyle = useAnimatedStyle(() => ({
    transform: [
      { translateY: bounce.value },
      { rotate: `${tilt.value}deg` },
    ],
  }));

  return (
    <View style={[s.row, style]}>
      <Animated.View style={animStyle}>
        <Image
          source={MOOD[variant]}
          style={[{ width: size, height: size }, imageStyle]}
          resizeMode="contain"
        />
      </Animated.View>
      {label ? (
        <AppText style={s.label}>{label}</AppText>
      ) : null}
    </View>
  );
}

const s = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  label: {
    fontFamily: fonts.serifBold,
    fontSize: 28,
    lineHeight: 32,
    color: colors.ink,
    flexShrink: 1,
  },
});
