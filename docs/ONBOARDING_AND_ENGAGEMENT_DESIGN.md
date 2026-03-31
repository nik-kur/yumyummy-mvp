# YumYummy — Onboarding & Engagement Design

**Status:** Approved  
**Date:** March 31, 2026  
**Based on:** Demand Curve B2C course principles (TTFV, activation, commitment alignment, hooks, retention motions)

---

## BLOCK 1: Onboarding Flow

### Core Principle

Value first, setup second. The user experiences the "aha moment" (logging a meal → seeing KBJU breakdown) before investing time in personalization. Demand Curve TTFV target: ≤60 seconds to first value.

### Phase 1 — Hook + First Value Demo

**Step 1: Welcome + Value Proposition**

```
👋 Hi! I'm YumYummy — your AI nutrition tracker.

Here's what makes me different:

⚡ Log meals in seconds — any format works:
📝 Text — "oatmeal with banana and coffee with milk"
🎤 Voice — just describe your meal in a voice message
📷 Photo — snap your plate, a label, or a barcode

🔬 Nerd-level precision:
Mention a brand (Danone, Chobani) or a place (Starbucks, Chipotle) — I'll search the web for official nutrition data.
No brand? No problem — I'll estimate from known averages.

🚀 Let's try it! Tell me what you had for your last meal.
Example: "cappuccino and a croissant at Starbucks"
```

**Step 2:** User sends their meal input. Bot starts processing via `agent_run_workflow`.

**Step 3a: "While I'm working" message (sent 2-3 sec after input):**

```
⏳ Got it! I'm analyzing your meal now.

If I'm searching for brand or restaurant data, this may take up to a minute — I'm checking real sources, not guessing.

While you wait — some food for thought (pun intended):

Research shows that 92% of people who start calorie counting quit within 2 weeks. The #1 reason isn't lack of motivation — it's the friction. Traditional apps take 15-20 minutes per day: search the database, pick the right item from 50 options, enter grams, repeat for every ingredient.

Here's another one: a study in the journal Obesity found that people who consistently track their food lose 2x more weight than those who don't — but "consistently" is the key word. The tracker has to be easy enough to actually use every day.

That's exactly why YumYummy exists. One message, and I handle the rest. Most meals take under 10 seconds to log.
```

**Step 3b: Second engagement message (sent 15 sec after 3a, only if result isn't ready):**

```
💡 By the way — a few things I can do that might surprise you:

If you're at a restaurant and can't decide what to order — send me the menu (photo or text) and I'll tell you the best option based on your remaining calorie and macro budget for the day.

Or just ask: "I'm at McDonald's, what should I get?" — and I'll figure it out.

Almost done with your analysis...
```

**Step 4:** Meal result delivered — standard KBJU breakdown (aha moment).

### Phase 1a — Interactive "My Menu" Tutorial

**Step 5: Introduce Save to My Menu**

```
💾 Like this meal? You can save it to your personal menu!

Tap the button below — next time you eat this, you'll log it in 2 taps instead of typing it out.
```

Button: `[💾 Save to My Menu]`

**Step 6: Explain + invite to try My Menu**

After user saves:

```
✅ Saved!

Your menu is your collection of go-to meals. Think of it as speed-dial for food tracking — breakfast you eat every day, your favorite lunch spot order, regular snacks.

Let's try it: tap [🍽 My Menu] below to see your saved meal and log it from there.
```

**Step 7: Guide through deletion**

After user logs from My Menu:

```
👍 See how fast that was? 2 taps — done.

Now let's clean up this duplicate. I'll show you how to edit or delete any logged meal — you'll need this later:

Tap [📊 Today] below.
```

Then guide: View logged meals → tap the duplicate → Delete.

After deletion:

```
🎯 Perfect! You now know how to:
— Log meals by typing, voice, or photo
— Save favorites to My Menu
— Log from My Menu in 2 taps
— View, edit, and delete meals

Now let's personalize your targets — takes about 30 seconds.
```

### Phase 2 — Personalization

Steps 8-12: Goal → Gender → Age/Height/Weight → Activity → KBJU Targets (confirm or manual) → Timezone

Same flow as before (mostly button taps).

### Phase 3 — Feature Guide + Trial Activation

**Step 13: Comprehensive Feature Guide**

```
📖 Here's everything YumYummy can do for you:

─────────────────
⚡ 10-Second Meal Logging — Any Format

Text — "2 eggs, toast with avocado, black coffee"
Voice — send a voice message describing your meal
Photo — snap your plate and I'll estimate KBJU
Barcode — photo of a product barcode = exact data
Nutrition label — photo of a label on packaging

─────────────────
🔬 Nerd-Level Precision — Not Just Rough Estimates

Mention a brand or restaurant:
"Cappuccino at Starbucks" → I search for official Starbucks nutrition data
"Epica yogurt 6%" → I find the manufacturer's numbers
"Tom Yum at Wagamama" → I look up the restaurant menu
No context? I estimate from known averages for that dish.

─────────────────
🍽 My Menu — Your Favorites on Speed-Dial

Save meals you eat often → log them in 2 taps next time.
You already tried this during setup!

─────────────────
🤔 What Should I Eat — Nutrition Advisor in Your Pocket

Not sure what to pick? Tell me your options:
"I'm at McDonald's, what should I order?"
"Need a snack, 300 kcal left"
"What should I cook for dinner? Need protein"
I'll suggest the best choice for your remaining daily budget.

─────────────────
📊 Track Your Progress

[📊 Today] — what you ate, what's left, progress bars
[📈 Week] — 7-day stats, daily averages, trends
[📤 Export] — download all your data as CSV

─────────────────

💡 This guide is always available — tap [📖 How to Use] in the menu anytime.
```

**Step 14:** New permanent `[📖 How to Use]` button in the main menu.

**Step 15: Trial Activation**

```
🎉 You're all set!

Activate your free trial:

✅ 3 days of full access
✅ Every feature unlocked
✅ No credit card required
✅ Cancel anytime — no strings

Just text, speak, or snap what you eat — I'll handle the rest.
```

Button: `[🚀 Start my free trial]`

After tap:

```
🎉 Free trial activated! Full access for 3 days.

Your next step: log your next meal whenever you're ready. I'm here 24/7.
```

---

## BLOCK 2: Trial Period Engagement (Days 0-3)

### Design Principles

1. Max 2 proactive messages/day
2. Every message delivers value (insight, tip, summary) — never just "use us"
3. Personalize based on actual behavior
4. Time to user's timezone
5. Skip/reduce if user is already active that day
6. Supportive tone, no guilt-tripping, no premature selling

### Day 0 (After onboarding + trial activated)

Only triggered AFTER onboarding is complete and trial started. Demo meal during onboarding doesn't count.

**After 1st real meal post-onboarding:**

```
✅ First meal tracked!

Come back after your next meal or snack — I'm keeping count.

Quick tip: the more meals you log, the more accurate your daily picture gets. Even a coffee or a small snack counts.
```

**Evening (~9 PM) — 1+ meals logged:**

```
📊 Here's your Day 1 summary:

(auto daily summary: calories/macros eaten vs targets, progress bars)

Good start! See you tomorrow 👋
```

**Evening (~9 PM) — 0 meals after onboarding:**

```
👋 Hey! You're all set up and your trial is running.

Try logging what you had for dinner — just type it, send a voice message, or snap a photo.

Even something simple like "pasta and a glass of juice" works.
```

### Day 1

**Morning (~9 AM):**

```
🌅 Good morning! New day, clean slate.

What's for breakfast? Just tell me — I'll handle the numbers.
```

**Feature tip (after 2nd meal ever, ~2 PM):**

```
💡 Quick tip: you can also send me a voice message.

Just record "Had a chicken salad and iced tea for lunch" — I'll understand it the same way.

Sometimes it's even faster than typing!
```

**Evening — 1+ meals:**

```
📊 Day 1 complete!

(daily summary)

You logged X meals today. That's a great start — building the habit is the hardest part, and you're already doing it.
```

**Evening — 0 meals:**

```
👋 I noticed no meals logged today — no stress!

Even if you don't track every meal, logging at least one helps you stay aware of your nutrition.

Try this: just tell me everything you remember eating today, all at once. I'll sort it out.
```

### Day 2

**Morning — logged yesterday:**

```
🔥 2-day streak!

You're building momentum. What's for breakfast?
```

**Morning — didn't log yesterday:**

```
👋 Hey! Quick reminder — even one logged meal per day keeps you on track.

What did you eat so far today? I'll take it from here.
```

**Feature tip (~2 PM, contextual):**

```
💡 Pro tip for packaged food:

Just snap a photo of the barcode on the package — I'll find the exact product and its nutrition data.

Works great for yogurts, snacks, drinks, cereals — anything with a barcode.
```

**Evening (always):**

```
📊 Day 2 stats:

(daily summary)

Quick insight: over the last 2 days, your average daily intake is X kcal. Your target is Y kcal — you're [on track / slightly over / under].

Patterns like this are exactly why tracking works — awareness changes behavior.
```

### Day 3 (Trial Ending Day)

**Activity threshold:** 2+ meal inputs during the trial = "active user"

**Morning — active user (NO trial/subscription mention):**

```
🔥 Day 3 — you're on a roll!

Here's something to try today: before your next meal, tap [🤔 What should I eat?]

Tell me where you're eating or what options you have, and I'll suggest what fits your remaining budget best. It's like having a nutritionist in your pocket.
```

**Morning — less active user:**

```
👋 Hey! I know life gets busy.

Here's the thing about nutrition tracking: it doesn't have to be perfect to be useful. Even logging 1-2 meals a day gives you a much clearer picture of your eating habits than guessing.

When you're ready, just tell me what you're eating — text, voice, or photo. I'm here.
```

**Evening — active user (2+ inputs) — CONVERSION MESSAGE:**

```
📊 Your 3-day YumYummy report:

─────────────────
🍽 Meals tracked: X
📅 Active days: Y out of 3
🎯 Within calorie target: Z% of days
🥩 Avg protein: Xg / Yg target
─────────────────

In 3 days, you've built the foundation of a nutrition tracking habit — something most people never manage with traditional apps.

Your data, your targets, your saved meals — everything is set up and working.

Your free trial ends today. To keep tracking and see your progress grow week over week, choose a plan:

🛡 Still in doubt? We offer a 30-day 100% money-back guarantee. If you don't love it — tap [💬 Support], and we'll send your refund within a day. No questions asked.
```

Button: `[⭐ View subscription plans]`

**Evening — less active user — CONVERSION MESSAGE:**

```
👋 Hey — your free trial wraps up today.

I know you haven't had a chance to fully explore everything yet, so here's a quick recap of what you'd keep with a subscription:

⚡ Log any meal in under 10 seconds — text, voice, or photo
🔬 Get real nutrition data from brands and restaurants
🍽 Build your personal menu for instant 2-tap logging
🤔 Ask "what should I eat?" for smart meal suggestions
📊 Daily and weekly tracking with insights

The hardest part of nutrition tracking is getting started — and you've already done that. Your targets are set, your account is ready.

🛡 Zero risk: 30-day money-back guarantee. Don't love it? Tap [💬 Support] and get a full refund within a day.

Keep your access:
```

Button: `[⭐ View subscription plans]`

---

## BLOCK 3: Post-Trial Win-Back Sequence

Every message includes a subscription button. Each uses a different psychological angle. Frequency decreases over time.

### T+0 (Trial just expired)

**Active user (2+ inputs):**

```
⏰ Your trial has ended.

In 3 days you tracked X meals and logged Y days of data. That's more consistent than 92% of people who try calorie counting!

Your data and saved meals are preserved — subscribe to keep your access and continue building on your progress.

🛡 30-day money-back guarantee — if it's not for you, just tap [💬 Support] for a full refund.
```

**Less active user:**

```
⏰ Your trial has ended.

Your account and settings are saved. Whenever you're ready to track your nutrition, everything is set up — just subscribe and start logging.
```

Button: `[⭐ View subscription plans]`

### T+1 day — Loss aversion

```
💡 Quick thought:

Your personal KBJU targets, your saved meals in My Menu, your tracking history — it's all still here.

Most nutrition apps take 5-10 minutes to set up from scratch. You've already done that work — don't let it go to waste.

Pick up where you left off:
```

Button: `[⭐ View subscription plans]`

### T+3 days — Untried feature angle

Based on what the user HASN'T tried during their trial. One of:

- Voice logging tip
- "What should I eat?" feature
- Barcode scanning

Button: `[⭐ View subscription plans]`

### T+7 days — Speed/ease

```
⏱ Still tracking nutrition?

The average person spends 15-20 minutes per day logging meals in traditional apps. YumYummy users spend under 2 minutes.

Your setup is still here. Your targets, your saved meals — all waiting.

🛡 Try it risk-free: 30-day money-back guarantee. Not happy? Full refund, no questions.

Ready to pick up where you left off?
```

Button: `[⭐ View subscription plans]`

### T+14 days — Fresh start

```
👋 It's been a couple of weeks.

If you're still thinking about getting your nutrition on track — I'm here. No judgment, no matter how long the break was.

Your account is ready. One tap to reactivate.

🛡 And remember — 30-day money-back guarantee. Zero risk.
```

Button: `[⭐ View subscription plans]`

### T+30 days — Final touch

```
🍽 Hey — just a final note from YumYummy.

Whenever you're ready to track your nutrition again, your account and settings are saved. I'll be here.

This is my last message — no more reminders after this. Take care!
```

Button: `[⭐ View subscription plans]`

**After T+30:** Complete silence. Respect the user.

---

## Implementation Notes

### New User Model Fields

- `features_used` — JSON string tracking which features user has tried (voice, barcode, my_menu, what_to_eat)
- `meals_count_trial` — count of meals logged during trial period
- `onboarding_step` — tracks current onboarding step for the new multi-phase flow

### New Main Menu Button

`[📖 How to Use]` added to the keyboard, always available.

### Notification Scheduler

Periodic task (runs every ~30 min) checks which users need which notification. Uses `notification_events` table to avoid duplicates.

### Feature Discovery

Tracked per-user. Feature tips sent contextually after relevant actions, not during onboarding.
