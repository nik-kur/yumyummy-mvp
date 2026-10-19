/**
 * 20 · Offer after the customer cancels the App Store sheet (Offer_C2,
 * `_closeup`). One product from the `pw_after_cancel` arm's flow. The close
 * button returns to the plans until preview mode (stage 6) takes it over.
 *
 * "Try it FREE" is the default headline; an arm can override it (`copy.headline`,
 * e.g. "50% OFF"). Shown only while the product carries a free trial — the
 * parent never opens this screen otherwise.
 */
import { Pressable, StyleSheet, Text } from 'react-native';
import type { AdaptyPaywallProduct } from 'react-native-adapty';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';

import { billed, trialDays, trialThenPrice, unitWord } from '@/billing/v3Pricing';
import { OnbButton } from '@/components/onb/OnbButton';
import type { PaywallArmConfig } from '@/config/types';
import { C, F } from '@/onb/theme';

import { OFFER_PHOTOS } from './copy';
import { DelayedClose } from './DelayedClose';
import { PhotoStage } from './PhotoStage';
import { LegalRow } from './PwParts';

interface Props {
  config: PaywallArmConfig;
  product: AdaptyPaywallProduct;
  purchasing: boolean;
  onBuy: () => void;
  onClose: () => void;
  onRestore: () => void;
}

export function OfferScreen({ config, product, purchasing, onBuy, onClose, onRestore }: Props) {
  const insets = useSafeAreaInsets();
  const spec = OFFER_PHOTOS[config.variant] ?? OFFER_PHOTOS.costa;
  const copy = config.copy;
  // `price_emphasis: billed` (default, App Review 3.1.2(c)): the amount that
  // will be charged is the big line, the trial the small one.
  const billedFirst = config.price_emphasis === 'billed';
  const days = trialDays(product);
  const headline = billedFirst ? `${billed(product)} / ${unitWord(product)}` : copy.headline ?? 'Try it FREE';
  const sub = billedFirst ? `after ${days} day${days === 1 ? '' : 's'} free · cancel anytime` : trialThenPrice(product);
  return (
    <PhotoStage
      photo={spec.photo}
      badge={spec.badge}
      fade={{ top: 400, above: 156, below: 138 }}
      label={
        spec.badge
          ? `A phone scanning a meal: ${spec.badge.title}, ${spec.badge.kcal} kcal`
          : 'A phone scanning a Costa coffee and a croissant, with the calories and source on screen'
      }
      overlay={
        <DelayedClose style={[s.closeSpot, { top: insets.top + 3 }]}>
          <Pressable onPress={onClose} style={s.close} hitSlop={8} accessibilityRole="button" accessibilityLabel="Close">
            <Svg width={20} height={20} viewBox="0 0 24 24" fill="none">
              <Path d="M18 6 6 18M6 6l12 12" stroke="#FFFFFF" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
            </Svg>
          </Pressable>
        </DelayedClose>
      }
    >
      <Text style={s.pill}>{copy.badge ?? 'Last offer'}</Text>
      <Text style={s.headline} accessibilityRole="header">
        {headline}
      </Text>
      <Text style={s.sub}>{sub}</Text>
      <OnbButton
        label={copy.cta ?? 'Continue'}
        onPress={onBuy}
        variant="brand"
        disabled={purchasing}
        style={{ marginTop: 22 }}
      />
      <Text style={s.foot}>{copy.footnote ?? 'No commitment · Cancel anytime'}</Text>
      <LegalRow onRestore={onRestore} color="rgba(255,255,255,0.55)" />
    </PhotoStage>
  );
}

const s = StyleSheet.create({
  closeSpot: { position: 'absolute', right: 12 },
  close: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(25,21,15,0.45)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  pill: {
    alignSelf: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.7)',
    borderRadius: 999,
    overflow: 'hidden',
    paddingVertical: 5,
    paddingHorizontal: 14,
    fontFamily: F.sansSemibold,
    fontSize: 14,
    lineHeight: 18,
    color: C.white,
  },
  headline: {
    marginTop: 10,
    textAlign: 'center',
    fontFamily: F.serif,
    fontSize: 52,
    lineHeight: 58,
    color: '#E3F08A',
  },
  sub: {
    marginTop: 4,
    textAlign: 'center',
    fontFamily: F.sans,
    fontSize: 16,
    lineHeight: 22,
    color: 'rgba(255,255,255,0.85)',
  },
  foot: {
    marginTop: 12,
    textAlign: 'center',
    fontFamily: F.sans,
    fontSize: 13,
    lineHeight: 18,
    color: 'rgba(255,255,255,0.7)',
  },
});
