# Trial Flow and Copy (Card Required, No Free Plan)

## 1) Product Rules

- No free tier.
- Trial only starts after plan selection + payment method + consent.
- Trial auto-converts to selected plan unless user cancels.
- User sees exact charge amount and timestamp before confirming.

## 2) Canonical Trial Flow

1. `paywall_viewed`
2. User picks plan (`plan_selected`)
3. Checkout screen with transparent terms
4. Payment method added
5. Consent checkbox/toggle accepted
6. Trial starts (`trial_started`)
7. Reminder at T-24h (`trial_reminder_sent`)
8. Reminder at T-3h (`trial_reminder_sent`)
9. Auto-conversion (`trial_converted_to_paid`) or cancel (`trial_canceled`)

## 3) Recommended Trial Length and Caps (Balanced launch)

- Trial length: 5 days
- Plan-specific trial caps:
  - Basic: 12 messages/day, 1 intensive/day
  - Plus: 20 messages/day, 2 intensive/day
  - Max: 35 messages/day, 4 intensive/day

Cap handling:

- When standard cap reached: block further requests until next local day.
- When intensive cap reached: fallback to standard mode only.
- Always provide visible remaining limits in UI.

## 4) UX Copy (RU)

### 4.1 Paywall headline

`Попробуй YumYummy бесплатно 5 дней`

Subline:

`Без бесплатной версии: доступ открывается через пробный период с автопродлением.`

### 4.2 Checkout disclosure (must be explicit)

`Сегодня: $0.00`

`Через 5 дней: $19.99 / месяц`

`Отмена в 1 клик до окончания пробного периода.`

### 4.3 Consent checkbox text

`Я согласен(на), что после окончания пробного периода с меня автоматически спишется стоимость выбранного тарифа, если я не отменю подписку заранее.`

### 4.4 Trial start confirmation

`Готово! Пробный период активирован до {trial_end_local_datetime}.`

`Мы напомним заранее до списания.`

### 4.5 Reminder T-24h

`Напоминание: ваш пробный период закончится через 24 часа.`

`Если не отменить, {date_time} будет списано ${price}.`

### 4.6 Reminder T-3h

`Пробный период заканчивается через 3 часа.`

`Следующее списание: ${price}.`

### 4.7 Cancel confirmation

`Подписка отменена. Доступ сохранится до {trial_end_local_datetime}.`

`Списаний больше не будет.`

## 5) Compliance and Risk Controls

- Keep a server-side `trial_end_at` timestamp in UTC.
- Use user timezone for all visible deadlines.
- Save consent proof (`consent_version`, timestamp, plan_id, price).
- Do not require support contact for cancellation.
- No hidden fees; tax behavior should be explicit in checkout.

## 6) Engineering Checklist for Payment Integration

- Persist fields:
  - `plan_id`
  - `billing_period`
  - `trial_started_at`
  - `trial_end_at`
  - `auto_renew_enabled`
  - `payment_method_last4` (optional display)
  - `consent_version`
- Add idempotent webhook handling for:
  - trial started
  - invoice paid
  - payment failed
  - cancellation
- Add daily cap counter reset based on user timezone.

## 7) AI Fair-Use Guardrails (Operational)

- The bot tracks estimated AI spend per user during the current billing cycle.
- Internal guardrails:
  - Trial: block after `$2` estimated AI cost
  - Active paid: block after `$10` estimated AI cost
- On guardrail hit:
  - Show explicit message with support contact.
  - Do not silently continue with degraded quality.
  - Keep audit log entry for support/manual review.

Recommended user-facing message on guardrail hit:

`Лимит использования достигнут. Пожалуйста, свяжитесь с поддержкой: @nik_kur`
