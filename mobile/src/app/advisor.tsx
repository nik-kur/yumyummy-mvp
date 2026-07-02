import { useRef, useState } from 'react';
import {
  View,
  StyleSheet,
  Pressable,
  TextInput,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Sparkles, X, ArrowUp } from 'lucide-react-native';

import { AppText } from '@/components/AppText';
import { Chip } from '@/components/Chip';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import * as api from '@/api/endpoints';
import { colors, radius, space } from '@/theme/tokens';
import { fonts } from '@/theme/typography';

interface SuggestionCard {
  name: string;
  kcal: number;
  protein: number;
  carbs: number;
  fat: number;
}
interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  card?: SuggestionCard;
}

const SUGGESTIONS = [
  'What should I eat for dinner?',
  'Am I getting enough protein?',
  'Ideas under 500 kcal',
];

const GREETING: Message = {
  id: 'greeting',
  role: 'assistant',
  text: 'Hi! I’m your nutrition advisor. Ask me what to eat next, how your day looks, or for ideas that fit your remaining budget.',
};

const DEMO_CARD: SuggestionCard = {
  name: 'Salmon & greens bowl',
  kcal: 560,
  protein: 42,
  carbs: 38,
  fat: 24,
};

let counter = 0;
const nextId = () => `m${++counter}`;

function Bubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';
  return (
    <View style={[styles.bubbleRow, isUser ? styles.rowEnd : styles.rowStart]}>
      <View style={[styles.bubble, isUser ? styles.userBubble : styles.assistantBubble]}>
        <AppText variant="body" color={isUser ? colors.white : colors.ink}>
          {message.text}
        </AppText>
        {message.card ? (
          <View style={styles.card}>
            <AppText variant="bodyStrong">{message.card.name}</AppText>
            <View style={styles.cardMacros}>
              <AppText variant="caption" color={colors.terracottaText}>
                {message.card.kcal} kcal
              </AppText>
              <AppText variant="caption" color={colors.protein}>
                P {message.card.protein}g
              </AppText>
              <AppText variant="caption" color={colors.fat}>
                F {message.card.fat}g
              </AppText>
              <AppText variant="caption" color={colors.carbs}>
                C {message.card.carbs}g
              </AppText>
            </View>
          </View>
        ) : null}
      </View>
    </View>
  );
}

export default function AdvisorScreen() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([GREETING]);
  const [input, setInput] = useState('');
  const [thinking, setThinking] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

  const send = async (raw: string) => {
    const textValue = raw.trim();
    if (!textValue || thinking) return;
    setInput('');
    const userMsg: Message = { id: nextId(), role: 'user', text: textValue };
    setMessages((prev) => [...prev, userMsg]);
    setThinking(true);
    try {
      const res = await api.agentRun({ text: textValue, force_intent: 'advice' });
      const reply: Message = {
        id: nextId(),
        role: 'assistant',
        text: res.message_text,
        card: DEMO_CARD,
      };
      setMessages((prev) => [...prev, reply]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: 'assistant', text: 'Sorry, I had trouble with that. Try again?' },
      ]);
    } finally {
      setThinking(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'bottom', 'left', 'right']}>
      <StatusBar style="dark" />
      <View style={styles.header}>
        <View style={styles.headerTitle}>
          <Sparkles size={18} color={colors.infoBlue} strokeWidth={1.5} />
          <AppText variant="title">AI Advisor</AppText>
        </View>
        <Pressable onPress={() => router.back()} hitSlop={10}>
          <X size={26} color={colors.inkMuted} strokeWidth={1.5} />
        </Pressable>
      </View>

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={8}
      >
        <ScrollView
          ref={scrollRef}
          style={styles.flex}
          contentContainerStyle={styles.messages}
          onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
          keyboardShouldPersistTaps="handled"
        >
          {messages.map((m) => (
            <Bubble key={m.id} message={m} />
          ))}
          {thinking ? (
            <View style={[styles.bubbleRow, styles.rowStart]}>
              <View style={[styles.bubble, styles.assistantBubble]}>
                <ActivityIndicator color={colors.inkMuted} />
              </View>
            </View>
          ) : null}

          {messages.length <= 1 ? (
            <View style={styles.suggestions}>
              {SUGGESTIONS.map((s) => (
                <Chip key={s} label={s} onPress={() => send(s)} />
              ))}
            </View>
          ) : null}
        </ScrollView>

        <View style={styles.inputBar}>
          <TextInput
            style={styles.input}
            placeholder="Ask anything about your nutrition…"
            placeholderTextColor={colors.inkFaint}
            value={input}
            onChangeText={setInput}
            onSubmitEditing={() => send(input)}
            returnKeyType="send"
          />
          <Pressable
            style={[styles.sendBtn, input.trim().length === 0 && styles.sendDisabled]}
            onPress={() => send(input)}
          >
            <ArrowUp size={22} color={colors.bg} strokeWidth={2} />
          </Pressable>
        </View>
        <AppText variant="caption" color={colors.inkFaint} style={styles.disclaimer}>
          AI advisor — informational only, not medical or dietary advice.
        </AppText>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  flex: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.hairline,
  },
  headerTitle: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  messages: { padding: space.lg, gap: space.md },
  bubbleRow: { flexDirection: 'row' },
  rowStart: { justifyContent: 'flex-start' },
  rowEnd: { justifyContent: 'flex-end' },
  bubble: { maxWidth: '86%', borderRadius: radius.lg, padding: space.base, gap: space.sm },
  userBubble: { backgroundColor: colors.terracotta, borderBottomRightRadius: radius.sm },
  assistantBubble: {
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.hairline,
    borderBottomLeftRadius: radius.sm,
  },
  card: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    padding: space.md,
    gap: space.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.hairline,
  },
  cardMacros: { flexDirection: 'row', gap: space.md, flexWrap: 'wrap' },
  suggestions: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm, marginTop: space.sm },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.hairline,
    backgroundColor: colors.surface,
  },
  input: {
    flex: 1,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.pill,
    paddingHorizontal: space.base,
    minHeight: 46,
    fontFamily: fonts.sans,
    fontSize: 16,
    color: colors.ink,
  },
  sendBtn: {
    width: 46,
    height: 46,
    borderRadius: radius.pill,
    backgroundColor: colors.ink,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendDisabled: { opacity: 0.4 },
  disclaimer: { textAlign: 'center', paddingHorizontal: space.lg, paddingBottom: space.sm },
});
