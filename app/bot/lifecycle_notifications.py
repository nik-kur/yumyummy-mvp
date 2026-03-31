"""
Lifecycle notification scheduler for YumYummy.
Sends engagement messages during trial and win-back messages after trial expiry.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, date, timezone
from typing import Optional

import pytz
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.db.session import SessionLocal
from app.models.user import User
from app.models.user_day import UserDay
from app.models.meal_entry import MealEntry
from app.models.notification_event import NotificationEvent

logger = logging.getLogger(__name__)

SCHEDULER_INTERVAL_SECONDS = 1800  # 30 minutes

# ─────────────────────────────────────────────────────────────────────────────
# Message templates
# ─────────────────────────────────────────────────────────────────────────────

DAY0_FIRST_MEAL = """✅ First meal tracked!

Come back after your next meal or snack — I'm keeping count.

Quick tip: the more meals you log, the more accurate your daily picture gets. Even a coffee or a small snack counts."""

DAY0_EVENING_ACTIVE = """📊 Here's your Day 1 summary:

{summary}

Good start! See you tomorrow 👋"""

DAY0_EVENING_INACTIVE = """👋 Hey! You're all set up and your trial is running.

Try logging what you had for dinner — just type it, send a voice message, or snap a photo.

Even something simple like "pasta and a glass of juice" works."""

DAY1_MORNING = """🌅 Good morning! New day, clean slate.

What's for breakfast? Just tell me — I'll handle the numbers."""

DAY1_FEATURE_VOICE = """💡 Quick tip: you can also send me a voice message.

Just record "Had a chicken salad and iced tea for lunch" — I'll understand it the same way.

Sometimes it's even faster than typing!"""

DAY1_EVENING_ACTIVE = """📊 Day 1 complete!

{summary}

You logged {meals_count} meals today. That's a great start — building the habit is the hardest part, and you're already doing it."""

DAY1_EVENING_INACTIVE = """👋 I noticed no meals logged today — no stress!

Even if you don't track every meal, logging at least one helps you stay aware of your nutrition.

Try this: just tell me everything you remember eating today, all at once. I'll sort it out."""

DAY2_MORNING_STREAK = """🔥 2-day streak!

You're building momentum. What's for breakfast?"""

DAY2_MORNING_NOSTREAK = """👋 Hey! Quick reminder — even one logged meal per day keeps you on track.

What did you eat so far today? I'll take it from here."""

DAY2_FEATURE_BARCODE = """💡 Pro tip for packaged food:

Just snap a photo of the barcode on the package — I'll find the exact product and its nutrition data.

Works great for yogurts, snacks, drinks, cereals — anything with a barcode."""

DAY2_EVENING = """📊 Day 2 stats:

{summary}

Quick insight: over the last 2 days, your average daily intake is {avg_cal:.0f} kcal. Your target is {target_cal:.0f} kcal — you're {status}.

Patterns like this are exactly why tracking works — awareness changes behavior."""

DAY3_MORNING_ACTIVE = """🔥 Day 3 — you're on a roll!

Here's something to try today: before your next meal, tap [🤔 What should I eat?]

Tell me where you're eating or what options you have, and I'll suggest what fits your remaining budget best. It's like having a nutritionist in your pocket."""

DAY3_MORNING_INACTIVE = """👋 Hey! I know life gets busy.

Here's the thing about nutrition tracking: it doesn't have to be perfect to be useful. Even logging 1-2 meals a day gives you a much clearer picture of your eating habits than guessing.

When you're ready, just tell me what you're eating — text, voice, or photo. I'm here."""

DAY3_EVENING_ACTIVE = """📊 Your 3-day YumYummy report:

─────────────────
🍽 Meals tracked: {meals_count}
📅 Active days: {active_days} out of 3
🎯 Within calorie target: {on_target_pct}% of days
🥩 Avg protein: {avg_protein:.0f}g / {target_protein:.0f}g target
─────────────────

In 3 days, you've built the foundation of a nutrition tracking habit — something most people never manage with traditional apps.

Your data, your targets, your saved meals — everything is set up and working.

Your free trial ends today. To keep tracking and see your progress grow week over week, choose a plan:

🛡 Still in doubt? We offer a 30-day 100% money-back guarantee. If you don't love it — tap 💬 Support, and we'll send your refund within a day. No questions asked."""

DAY3_EVENING_INACTIVE = """👋 Hey — your free trial wraps up today.

I know you haven't had a chance to fully explore everything yet, so here's a quick recap of what you'd keep with a subscription:

⚡ Log any meal in under 10 seconds — text, voice, or photo
🔬 Get real nutrition data from brands and restaurants
🍽 Build your personal menu for instant 2-tap logging
🤔 Ask "what should I eat?" for smart meal suggestions
📊 Daily and weekly tracking with insights

The hardest part of nutrition tracking is getting started — and you've already done that. Your targets are set, your account is ready.

🛡 Zero risk: 30-day money-back guarantee. Don't love it? Tap 💬 Support and get a full refund within a day.

Keep your access:"""

WINBACK_T0_ACTIVE = """⏰ Your trial has ended.

In {trial_days} days you tracked {meals_count} meals and logged {active_days} days of data. That's more consistent than 92% of people who try calorie counting!

Your data and saved meals are preserved — subscribe to keep your access and continue building on your progress.

🛡 30-day money-back guarantee — if it's not for you, just tap 💬 Support for a full refund."""

WINBACK_T0_INACTIVE = """⏰ Your trial has ended.

Your account and settings are saved. Whenever you're ready to track your nutrition, everything is set up — just subscribe and start logging."""

WINBACK_T1 = """💡 Quick thought:

Your personal KBJU targets, your saved meals in My Menu, your tracking history — it's all still here.

Most nutrition apps take 5-10 minutes to set up from scratch. You've already done that work — don't let it go to waste.

Pick up where you left off:"""

WINBACK_T3_VOICE = """🎤 Did you know you can track meals by voice?

Just send a voice message: "For lunch I had a Caesar salad and sparkling water" — and I'll log everything with full KBJU breakdown.

Sometimes it's even faster than typing. Try it with a subscription:"""

WINBACK_T3_WHAT_TO_EAT = """🤔 Here's a feature you haven't tried yet:

Tap "What should I eat?" and tell me where you are or what options you have. I'll analyze your remaining daily budget and suggest the best pick.

"I'm at Subway, what should I get?" — and I'll tell you exactly.

Unlock all features:"""

WINBACK_T3_BARCODE = """📷 Quick tip you might have missed:

For any packaged product, just snap a photo of the barcode. I'll find the exact product in the database — no typing needed.

Works for yogurts, cereals, snacks, drinks — anything with a barcode.

Get full access:"""

WINBACK_T7 = """⏱ Still tracking nutrition?

The average person spends 15-20 minutes per day logging meals in traditional apps. YumYummy users spend under 2 minutes.

Your setup is still here. Your targets, your saved meals — all waiting.

🛡 Try it risk-free: 30-day money-back guarantee. Not happy? Full refund, no questions.

Ready to pick up where you left off?"""

WINBACK_T14 = """👋 It's been a couple of weeks.

If you're still thinking about getting your nutrition on track — I'm here. No judgment, no matter how long the break was.

Your account is ready. One tap to reactivate.

🛡 And remember — 30-day money-back guarantee. Zero risk."""

WINBACK_T30 = """🍽 Hey — just a final note from YumYummy.

Whenever you're ready to track your nutrition again, your account and settings are saved. I'll be here.

This is my last message — no more reminders after this. Take care!"""

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _user_local_now(user: User) -> datetime:
    tz = pytz.timezone(user.timezone or "UTC")
    return datetime.now(tz)


def _user_local_hour(user: User) -> int:
    return _user_local_now(user).hour


def _was_sent(db, telegram_id: str, event_type: str) -> bool:
    return db.query(NotificationEvent).filter(
        NotificationEvent.telegram_id == telegram_id,
        NotificationEvent.event_type == event_type,
    ).first() is not None


def _record_sent(db, telegram_id: str, event_type: str, extra_data: Optional[str] = None):
    db.add(NotificationEvent(
        telegram_id=telegram_id,
        event_type=event_type,
        extra_data=extra_data,
    ))
    db.commit()


def _trial_day(user: User) -> Optional[int]:
    """0-indexed day of trial. None if no trial."""
    if not user.trial_started_at:
        return None
    now = datetime.now(timezone.utc)
    started = user.trial_started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    delta = now - started
    return delta.days


def _days_since_trial_end(user: User) -> Optional[int]:
    if not user.trial_ends_at:
        return None
    now = datetime.now(timezone.utc)
    ends = user.trial_ends_at
    if ends.tzinfo is None:
        ends = ends.replace(tzinfo=timezone.utc)
    if now < ends:
        return None
    delta = now - ends
    return delta.days


def _get_meals_count_today(db, user: User) -> int:
    today = date.today()
    user_day = db.query(UserDay).filter(
        UserDay.user_id == user.id,
        UserDay.date == today,
    ).first()
    if not user_day:
        return 0
    return db.query(MealEntry).filter(MealEntry.user_day_id == user_day.id).count()


def _get_total_meals_trial(user: User) -> int:
    return user.meals_count_trial or 0


def _has_active_subscription(user: User) -> bool:
    if not user.subscription_ends_at:
        return False
    now = datetime.now(timezone.utc)
    ends = user.subscription_ends_at
    if ends.tzinfo is None:
        ends = ends.replace(tzinfo=timezone.utc)
    return ends > now and user.subscription_plan_id is not None


def _build_subscription_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⭐ View subscription plans",
            callback_data="show_paywall_from_notification",
        )]
    ])


def _build_day_summary_text(db, user: User, target_date: Optional[date] = None) -> str:
    """Build a text summary of nutrition for a given day."""
    target = target_date or date.today()
    user_day = db.query(UserDay).filter(
        UserDay.user_id == user.id,
        UserDay.date == target,
    ).first()

    if not user_day:
        return "No data for today yet."

    cal = user_day.total_calories or 0
    prot = user_day.total_protein_g or 0
    fat = user_day.total_fat_g or 0
    carbs = user_day.total_carbs_g or 0

    t_cal = user.target_calories or 2000
    t_prot = user.target_protein_g or 120
    t_fat = user.target_fat_g or 65
    t_carbs = user.target_carbs_g or 250

    return (
        f"🔥 Calories: {cal:.0f} / {t_cal:.0f} kcal\n"
        f"🥩 Protein: {prot:.0f} / {t_prot:.0f} g\n"
        f"🧈 Fat: {fat:.0f} / {t_fat:.0f} g\n"
        f"🍞 Carbs: {carbs:.0f} / {t_carbs:.0f} g"
    )


def _get_active_days_count(db, user: User, days_back: int = 3) -> int:
    """Count how many of the last N days had at least 1 meal."""
    today = date.today()
    count = 0
    for i in range(days_back):
        d = today - timedelta(days=i)
        user_day = db.query(UserDay).filter(
            UserDay.user_id == user.id,
            UserDay.date == d,
        ).first()
        if user_day:
            meal_count = db.query(MealEntry).filter(MealEntry.user_day_id == user_day.id).count()
            if meal_count > 0:
                count += 1
    return count


def _get_avg_calories(db, user: User, days_back: int = 2) -> float:
    """Average daily calories over last N days."""
    today = date.today()
    total = 0.0
    counted = 0
    for i in range(days_back):
        d = today - timedelta(days=i)
        user_day = db.query(UserDay).filter(
            UserDay.user_id == user.id,
            UserDay.date == d,
        ).first()
        if user_day and (user_day.total_calories or 0) > 0:
            total += user_day.total_calories
            counted += 1
    return total / max(counted, 1)


def _get_avg_protein(db, user: User, days_back: int = 3) -> float:
    today = date.today()
    total = 0.0
    counted = 0
    for i in range(days_back):
        d = today - timedelta(days=i)
        user_day = db.query(UserDay).filter(
            UserDay.user_id == user.id,
            UserDay.date == d,
        ).first()
        if user_day and (user_day.total_protein_g or 0) > 0:
            total += user_day.total_protein_g
            counted += 1
    return total / max(counted, 1)


def _get_on_target_days_pct(db, user: User, days_back: int = 3) -> int:
    """Percentage of days where calories were within ±15% of target."""
    today = date.today()
    target = user.target_calories or 2000
    on_target = 0
    total = 0
    for i in range(days_back):
        d = today - timedelta(days=i)
        user_day = db.query(UserDay).filter(
            UserDay.user_id == user.id,
            UserDay.date == d,
        ).first()
        if user_day and (user_day.total_calories or 0) > 0:
            total += 1
            if abs(user_day.total_calories - target) <= target * 0.15:
                on_target += 1
    if total == 0:
        return 0
    return round(on_target / total * 100)


def _logged_yesterday(db, user: User) -> bool:
    yesterday = date.today() - timedelta(days=1)
    user_day = db.query(UserDay).filter(
        UserDay.user_id == user.id,
        UserDay.date == yesterday,
    ).first()
    if not user_day:
        return False
    return db.query(MealEntry).filter(MealEntry.user_day_id == user_day.id).count() > 0


def _pick_winback_t3_feature(user: User) -> str:
    """Pick an untried feature for the T+3 win-back message. Default to voice."""
    try:
        features = json.loads(user.features_used) if user.features_used else {}
    except (json.JSONDecodeError, TypeError):
        features = {}

    if not features.get("voice", False):
        return "voice"
    if not features.get("barcode", False):
        return "barcode"
    if not features.get("what_to_eat", False):
        return "what_to_eat"
    return "voice"


# ─────────────────────────────────────────────────────────────────────────────
# Sending
# ─────────────────────────────────────────────────────────────────────────────


async def _send_notification(
    bot: Bot,
    telegram_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> bool:
    """Send a Telegram message. Returns True on success."""
    try:
        await bot.send_message(chat_id=telegram_id, text=text, reply_markup=reply_markup)
        return True
    except Exception as e:
        logger.warning(f"Failed to send notification to {telegram_id}: {e}")
        return False


async def send_first_meal_notification(bot: Bot, telegram_id: str):
    """Send the first meal congratulation. Called from run_bot after first meal post-onboarding."""
    db = SessionLocal()
    try:
        if _was_sent(db, telegram_id, "day0_first_meal"):
            return
        sent = await _send_notification(bot, int(telegram_id), DAY0_FIRST_MEAL)
        if sent:
            _record_sent(db, telegram_id, "day0_first_meal")
    finally:
        db.close()


async def send_feature_tip_voice(bot: Bot, telegram_id: str):
    """Send voice feature tip after 2nd meal. Called from run_bot."""
    db = SessionLocal()
    try:
        if _was_sent(db, telegram_id, "day1_feature_tip_voice"):
            return
        sent = await _send_notification(bot, int(telegram_id), DAY1_FEATURE_VOICE)
        if sent:
            _record_sent(db, telegram_id, "day1_feature_tip_voice")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Scheduler core
# ─────────────────────────────────────────────────────────────────────────────


async def run_notification_scheduler(bot: Bot):
    """Main scheduler loop. Runs as a background task."""
    logger.info("Lifecycle notification scheduler started")
    while True:
        try:
            await _check_and_send_notifications(bot)
        except Exception as e:
            logger.error(f"Notification scheduler error: {e}", exc_info=True)
        await asyncio.sleep(SCHEDULER_INTERVAL_SECONDS)


async def _check_and_send_notifications(bot: Bot):
    """Single pass: check all users and send due notifications."""
    db = SessionLocal()
    try:
        users = db.query(User).filter(
            User.onboarding_completed == True,  # noqa: E712
            User.trial_started_at.isnot(None),
        ).all()

        for user in users:
            try:
                await _process_user_notifications(bot, db, user)
            except Exception as e:
                logger.error(
                    f"Error processing notifications for user {user.telegram_id}: {e}",
                    exc_info=True,
                )
    finally:
        db.close()


async def _process_user_notifications(bot: Bot, db, user: User):
    tg_id = user.telegram_id
    trial_day = _trial_day(user)
    days_after = _days_since_trial_end(user)
    hour = _user_local_hour(user)

    # Skip users with an active paid subscription (they don't need lifecycle nudges)
    if _has_active_subscription(user):
        return

    # ── Trial-period notifications ──────────────────────────────────────
    if trial_day is not None and days_after is None:
        await _process_trial_notifications(bot, db, user, tg_id, trial_day, hour)

    # ── Post-trial win-back ─────────────────────────────────────────────
    if days_after is not None and not _has_active_subscription(user):
        await _process_winback_notifications(bot, db, user, tg_id, days_after, hour)


async def _process_trial_notifications(
    bot: Bot, db, user: User, tg_id: str, trial_day: int, hour: int
):
    meals_today = _get_meals_count_today(db, user)

    # ── Day 0 ───────────────────────────────────────────────────────────

    if trial_day == 0:
        # Evening (9 PM window: hours 21–22)
        if 21 <= hour < 23:
            if meals_today > 0 and not _was_sent(db, tg_id, "day0_evening_active"):
                summary = _build_day_summary_text(db, user)
                text = DAY0_EVENING_ACTIVE.format(summary=summary)
                if await _send_notification(bot, int(tg_id), text):
                    _record_sent(db, tg_id, "day0_evening_active")
            elif meals_today == 0 and not _was_sent(db, tg_id, "day0_evening_inactive"):
                if await _send_notification(bot, int(tg_id), DAY0_EVENING_INACTIVE):
                    _record_sent(db, tg_id, "day0_evening_inactive")

    # ── Day 1 ───────────────────────────────────────────────────────────

    elif trial_day == 1:
        # Morning (9 AM window: hours 9–10)
        if 9 <= hour < 11 and not _was_sent(db, tg_id, "day1_morning"):
            if await _send_notification(bot, int(tg_id), DAY1_MORNING):
                _record_sent(db, tg_id, "day1_morning")

        # Evening (9 PM window: hours 21–22)
        if 21 <= hour < 23:
            if meals_today > 0 and not _was_sent(db, tg_id, "day1_evening_active"):
                summary = _build_day_summary_text(db, user)
                text = DAY1_EVENING_ACTIVE.format(
                    summary=summary,
                    meals_count=meals_today,
                )
                if await _send_notification(bot, int(tg_id), text):
                    _record_sent(db, tg_id, "day1_evening_active")
            elif meals_today == 0 and not _was_sent(db, tg_id, "day1_evening_inactive"):
                if await _send_notification(bot, int(tg_id), DAY1_EVENING_INACTIVE):
                    _record_sent(db, tg_id, "day1_evening_inactive")

    # ── Day 2 ───────────────────────────────────────────────────────────

    elif trial_day == 2:
        # Morning (9 AM window)
        if 9 <= hour < 11:
            if _logged_yesterday(db, user) and not _was_sent(db, tg_id, "day2_morning_streak"):
                if await _send_notification(bot, int(tg_id), DAY2_MORNING_STREAK):
                    _record_sent(db, tg_id, "day2_morning_streak")
            elif not _logged_yesterday(db, user) and not _was_sent(db, tg_id, "day2_morning_nostreak"):
                if await _send_notification(bot, int(tg_id), DAY2_MORNING_NOSTREAK):
                    _record_sent(db, tg_id, "day2_morning_nostreak")

        # Feature tip: barcode (2 PM window: hours 14–16)
        if 14 <= hour < 16 and not _was_sent(db, tg_id, "day2_feature_tip_barcode"):
            if await _send_notification(bot, int(tg_id), DAY2_FEATURE_BARCODE):
                _record_sent(db, tg_id, "day2_feature_tip_barcode")

        # Evening (9 PM window)
        if 21 <= hour < 23 and not _was_sent(db, tg_id, "day2_evening"):
            avg_cal = _get_avg_calories(db, user, days_back=2)
            target_cal = user.target_calories or 2000
            diff = avg_cal - target_cal
            if abs(diff) < target_cal * 0.05:
                status = "right on target 🎯"
            elif diff > 0:
                status = f"{diff:.0f} kcal above target"
            else:
                status = f"{abs(diff):.0f} kcal below target"
            summary = _build_day_summary_text(db, user)
            text = DAY2_EVENING.format(
                summary=summary,
                avg_cal=avg_cal,
                target_cal=target_cal,
                status=status,
            )
            if await _send_notification(bot, int(tg_id), text):
                _record_sent(db, tg_id, "day2_evening")

    # ── Day 3 (trial ending) ────────────────────────────────────────────

    elif trial_day >= 3:
        total_meals = _get_total_meals_trial(user)
        kb = _build_subscription_button()

        # Morning (9 AM window)
        if 9 <= hour < 11:
            if total_meals >= 2 and not _was_sent(db, tg_id, "day3_morning_active"):
                if await _send_notification(bot, int(tg_id), DAY3_MORNING_ACTIVE):
                    _record_sent(db, tg_id, "day3_morning_active")
            elif total_meals < 2 and not _was_sent(db, tg_id, "day3_morning_inactive"):
                if await _send_notification(bot, int(tg_id), DAY3_MORNING_INACTIVE):
                    _record_sent(db, tg_id, "day3_morning_inactive")

        # Evening (9 PM window)
        if 21 <= hour < 23:
            if total_meals >= 2 and not _was_sent(db, tg_id, "day3_evening_active"):
                active_days = _get_active_days_count(db, user, days_back=3)
                on_target_pct = _get_on_target_days_pct(db, user, days_back=3)
                avg_protein = _get_avg_protein(db, user, days_back=3)
                target_protein = user.target_protein_g or 120
                text = DAY3_EVENING_ACTIVE.format(
                    meals_count=total_meals,
                    active_days=active_days,
                    on_target_pct=on_target_pct,
                    avg_protein=avg_protein,
                    target_protein=target_protein,
                )
                if await _send_notification(bot, int(tg_id), text, reply_markup=kb):
                    _record_sent(db, tg_id, "day3_evening_active")
            elif total_meals < 2 and not _was_sent(db, tg_id, "day3_evening_inactive"):
                if await _send_notification(bot, int(tg_id), DAY3_EVENING_INACTIVE, reply_markup=kb):
                    _record_sent(db, tg_id, "day3_evening_inactive")


async def _process_winback_notifications(
    bot: Bot, db, user: User, tg_id: str, days_after: int, hour: int
):
    total_meals = _get_total_meals_trial(user)
    kb = _build_subscription_button()

    # T+0: immediately when trial expires
    if days_after == 0:
        if total_meals >= 2 and not _was_sent(db, tg_id, "winback_t0_active"):
            started = user.trial_started_at
            ended = user.trial_ends_at
            trial_days = 3
            if started and ended:
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                if ended.tzinfo is None:
                    ended = ended.replace(tzinfo=timezone.utc)
                trial_days = max((ended - started).days, 1)
            active_days = _get_active_days_count(db, user, days_back=trial_days)
            text = WINBACK_T0_ACTIVE.format(
                trial_days=trial_days,
                meals_count=total_meals,
                active_days=active_days,
            )
            if await _send_notification(bot, int(tg_id), text, reply_markup=kb):
                _record_sent(db, tg_id, "winback_t0_active")
        elif total_meals < 2 and not _was_sent(db, tg_id, "winback_t0_inactive"):
            if await _send_notification(bot, int(tg_id), WINBACK_T0_INACTIVE, reply_markup=kb):
                _record_sent(db, tg_id, "winback_t0_inactive")

    # T+1
    if days_after >= 1 and not _was_sent(db, tg_id, "winback_t1"):
        if 9 <= hour < 15:
            if await _send_notification(bot, int(tg_id), WINBACK_T1, reply_markup=kb):
                _record_sent(db, tg_id, "winback_t1")

    # T+3: feature-based
    if days_after >= 3 and not _was_sent(db, tg_id, "winback_t3"):
        if 9 <= hour < 15:
            feature = _pick_winback_t3_feature(user)
            if feature == "voice":
                text = WINBACK_T3_VOICE
            elif feature == "barcode":
                text = WINBACK_T3_BARCODE
            else:
                text = WINBACK_T3_WHAT_TO_EAT
            if await _send_notification(bot, int(tg_id), text, reply_markup=kb):
                _record_sent(db, tg_id, "winback_t3")

    # T+7
    if days_after >= 7 and not _was_sent(db, tg_id, "winback_t7"):
        if 9 <= hour < 15:
            if await _send_notification(bot, int(tg_id), WINBACK_T7, reply_markup=kb):
                _record_sent(db, tg_id, "winback_t7")

    # T+14
    if days_after >= 14 and not _was_sent(db, tg_id, "winback_t14"):
        if 9 <= hour < 15:
            if await _send_notification(bot, int(tg_id), WINBACK_T14, reply_markup=kb):
                _record_sent(db, tg_id, "winback_t14")

    # T+30: final message
    if days_after >= 30 and not _was_sent(db, tg_id, "winback_t30"):
        if 9 <= hour < 15:
            if await _send_notification(bot, int(tg_id), WINBACK_T30):
                _record_sent(db, tg_id, "winback_t30")
