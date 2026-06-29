import { Text as RNText, type TextProps, type StyleProp, type TextStyle } from 'react-native';
import { text, type TextVariant } from '@/theme/typography';

interface AppTextProps extends TextProps {
  variant?: TextVariant;
  color?: string;
  center?: boolean;
  style?: StyleProp<TextStyle>;
}

export function AppText({ variant = 'body', color, center, style, ...rest }: AppTextProps) {
  return (
    <RNText
      {...rest}
      style={[text[variant], color ? { color } : null, center ? { textAlign: 'center' } : null, style]}
    />
  );
}
