# Owner Action Plan — что делаешь лично (click-by-click)

Порядок = приоритет/зависимости. Значения из аудита подставлены.

Ключевые ID:
- Apple App ID (числовой): **6785363037** · Apple Team ID: **WZAXY7M3G5**
- Bundle ID: **ai.yumyummy.app**
- Render прод: **yumyummy-mvp-eu** — https://dashboard.render.com/web/srv-d7u65glckfvc73elunn0
- Neon: проект **YumYummy-dev** (`hidden-unit-26706255`), ветка **production**
- Adapty iOS SDK key (публичный, уже в билде): `public_live_yn88NC6V...`

---

## 1. Render — проверить env прод-сервиса (15 мин)
1. https://dashboard.render.com → сервис **yumyummy-mvp-eu** → вкладка **Environment**.
2. Проверь/добавь переменные (Add Environment Variable → Save changes → передеплоит):
   - `AUTH_EMAIL_DEBUG_RETURN_CODE` → **false** (или удалить). ⚠️ Если true — коды входа по email возвращаются в ответе API = вход за любого. Критично.
   - `INTERNAL_API_TOKEN` →任意 длинный секрет (32+ симв). Теперь без него легаси `/ai/*` и CRUD отвечают 401 (это правильно). Тот же токен должен стоять у Telegram-бота (сервис `yumyummy-mvp-bot-eu`).
   - `JWT_SECRET` → есть, уникальный для прода.
   - `ADAPTY_API_KEY` (секретный, не публичный) + `ADAPTY_WEBHOOK_SECRET`.
   - `SENTRY_DSN` (бэкенд), `OPENAI_API_KEY`, `GEMINI_API_KEY`, `PERPLEXITY_API_KEY`.
   - `BILLING_PAYWALL_ENABLED` → **true**.
   - `DATABASE_URL` → открой значение, убедись что хост содержит **`-pooler`** (напр. `...-pooler.eu-central-1.aws.neon.tech`). Если хоста без `-pooler` — замени на pooled (см. Neon шаг 2).
3. Опционально: `RATE_LIMIT_ENABLED=true`, `GLOBAL_DAILY_LLM_COST_CAP_USD=200` (в коде дефолты уже такие).

## 2. Neon — retention + защита ветки (10 мин)
1. https://console.neon.tech → проект **YumYummy-dev**.
2. **Settings → Storage (History retention)** → подними с 6 ч до **7 дней** (может потребовать платный план: Settings → Billing → Launch/Scale).
3. **Branches → production → ⋯ → Set as protected** (защита от случайного удаления/reset).
4. Pooled-строка: **Dashboard → Connect** (кнопка сверху) → в диалоге включи **Connection pooling** → скопируй строку с `-pooler` → это значение для `DATABASE_URL` на Render (шаг 1).
5. Опц.: переименовать проект в `YumYummy` (Settings → General). Некритично — ветка уже зовётся `production`.

## 3. LLM billing-алерты (10 мин)
- **OpenAI:** https://platform.openai.com/settings/organization/limits → Usage limits → задай Monthly budget + email-алерт.
- **Google Gemini:** https://console.cloud.google.com → Billing → Budgets & alerts → Create budget на проект с Gemini API.
- **Perplexity:** https://www.perplexity.ai/settings/api → выставь лимит/автопополнение с потолком.

## 4. Sentry auth token → EAS (10 мин)
1. https://sentry.io → своя организация (**yumyummy**) → **Settings → Auth Tokens** (Organization Tokens) → **Create New Token**. Scopes: `project:read`, `project:releases`, `org:read`. Скопируй токен (показывается один раз).
2. В терминале из папки `mobile`:
   ```bash
   eas env:create --environment production --name SENTRY_AUTH_TOKEN --value "ТОКЕН" --visibility sensitive
   eas env:create --environment preview    --name SENTRY_AUTH_TOKEN --value "ТОКЕН" --visibility sensitive
   ```
   (или через https://expo.dev → проект yumyummy-app → **Environment Variables**).
   Проверка: в логе `eas build` появится строка про upload source maps. Без токена билд не падает, но крэши останутся минифицированными.

## 5. Атрибуция — завести аккаунты и ключи
Проще идти «от Adapty»: открой в Adapty страницу интеграции — она перечисляет, какие поля ей нужны, и ты идёшь за ними.

### 5a. AppsFlyer (15 мин)
1. Регистрация: https://www.appsflyer.com → Start now (Sign up). Тариф Zero подходит для старта.
2. **Add app** → iOS → App Store ID **6785363037** (можно ссылкой на App Store; если приложение ещё не опубликовано — создай app вручную, привяжешь позже).
3. Dev key: в приложении → **Configuration → App settings → SDK → Dev key**. Скопируй.
4. Добавь ключи в `mobile/eas.json` в `production.env` и `preview.env` (или как EAS env):
   - `EXPO_PUBLIC_APPSFLYER_DEV_KEY` = dev key
   - `EXPO_PUBLIC_APPSFLYER_APP_ID` = `6785363037`
   Если оставишь пустыми — атрибуция просто no-op, приложение работает.

### 5b. Meta (Facebook) app registration (20 мин)
1. https://developers.facebook.com/apps → **Create App** (или используй существующий, если есть). Тип: обычно “Consumer/Other”.
2. Внутри app → **Add Platform → iOS** → Bundle ID `ai.yumyummy.app`, iPhone Store ID `6785363037`.
3. Возьми **App ID** и **App Secret** (Settings → Basic). Это то, что попросит Adapty для интеграции Meta.
4. (Web-пиксель `826914203808503` у тебя уже есть на лендинге — это отдельная сущность, для in-app конверсий нужна именно app registration + Adapty S2S.)

### 5c. TikTok app registration (20 мин)
1. https://ads.tiktok.com → **Assets → Events → Manage → App** → зарегистрируй приложение (iOS, App Store ID `6785363037`), выбери MMP = **AppsFlyer** (S2S) либо TikTok SDK.
2. Возьми **TikTok App ID** (и, если Adapty попросит, access token) — понадобится в Adapty.

## 6. Adapty dashboard (20 мин + тест)
1. https://app.adapty.io → **Integrations**.
   - **AppsFlyer** → вставь Dev key (и App ID) → Enable.
   - **Facebook Ads / Meta** → вставь Meta App ID + App Secret → Enable (server-to-server, SDK не нужен).
   - **TikTok** → вставь TikTok App ID/токен → Enable.
   Эти интеграции шлют события покупок в рекламные сети напрямую от Adapty — так кампании оптимизируются даже при iOS-приватности.
2. **Integrations → Webhook** (или App settings → Webhooks): убедись, что URL = `https://yumyummy-mvp-eu.onrender.com/webhooks/adapty` и секрет совпадает с `ADAPTY_WEBHOOK_SECRET` на Render.
3. **Products/Paywalls:** проверь, что product ID совпадают с кодом: `ai.yumyummy.app.yearly`, `ai.yumyummy.app.monthly`, `ai.yumyummy.app.weekly_upd`, и что placement’ы `main`/`onboarding` заполнены.
4. **E2E-тест** (после TestFlight-билда, шаг 8): sandbox-покупка → вход через Apple → в приложении `access_status: active`; проверь restore purchases; отмену триала. В Adapty (Events) и PostHog должны появиться `subscription_*`.

## 7. App Store Connect — листинг (30–40 мин)
https://appstoreconnect.apple.com → **Apps → YumYummy → (версия 1.0)**.
1. **App Information / Pricing:** категории Health & Fitness (primary) + Food & Drink; цена/подписки уже одобрены.
2. **Метаданные** (вкладка версии) — бери из `docs/aso/app-store-listing.md`:
   - Name: `YumYummy: AI Calorie Tracker`
   - Subtitle: `Macro & food log, real data`
   - Keywords: `counter,nutrition,diet,weight,loss,protein,carb,meal,fasting,health,fitness,kcal,scanner,coach`
   - Description, Promotional Text, What's New — оттуда же.
3. **Скриншоты + App Preview:** 6.9" (1290×2796), 7 кадров по `docs/aso/screenshots-storyboard.md`. Загрузи в слот 6.9" (остальные размеры Apple масштабирует).
4. **Support URL:** `https://yumyummy.ai/support` · **Privacy Policy URL:** проверь что открывается.
5. ⚠️ **App Privacy → "Data Used to Track You"**: т.к. в билде ATT + AppsFlyer, объяви трекинг (Identifiers → IDFA/Device ID, Usage Data → «Used to Track You»). App Information → **App Privacy → Edit**. Без этого — реджект.

## 8. Сборка → сабмит → раскатка
Из папки `mobile` (нужны твои Apple-креды/2FA):
```bash
npm install                                   # новые нативные модули уже в package.json
npx tsc --noEmit && npm run lint              # sanity (сейчас чисто)
eas build --platform ios --profile production # полный нативный билд (ATT+AppsFlyer)
eas submit --platform ios --profile production --latest
```
1. В логе билда проверь строку про **Sentry source maps upload**.
2. **TestFlight смоук** (реальное устройство): ATT-промпт при первом запуске → вход Apple → лог еды текст/фото/голос («Logged.» + бейдж источника) → advisor → sandbox-покупка/cancel/restore → тестовый крэш и проверка читаемого стэка в Sentry (release `yumyummy@1.0.0`).
3. **Submit for Review** в App Store Connect.
4. После апрува — **Phased Release** (7-дневная постепенная раскатка): в разделе версии включи “Release update over 7-day period”.

## 9. Первые 24–48 ч (перед включением платного трафика)
- Sentry: crash-free sessions ≥ 99.5%.
- Render Logs: 5xx, `[RATELIMIT]` (429), срабатывания cost-cap.
- PostHog: воронка + `meal_logged` (см. `docs/analytics/launch-dashboard.md`).
- LLM-спенд против дневного капа.
- Только после стабильности — включай кампании Meta/TikTok.
