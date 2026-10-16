# Онбординг и пейвол V3: журнал реализации

Спецификация: [knowledge/onboarding-v3-implementation-2026-10.md](knowledge/onboarding-v3-implementation-2026-10.md) (раздел «Договорённости 15 октября» главнее). Дизайн: канвас https://claude.ai/artifact/LxWpJAaF5xDcZmAynawjNM, страница «V3 · правки 14 окт». Читать живой канвас (Artifact read): локальная копия `design/canvas_backup` от 15 окт устарела — в ней нет экрана 0 (`V3_Splash`, `V3_Splash_story`).

Ветка: `onboarding-v3` от main. Коммитить в ветку можно без спроса; push, PR, merge, Adapty, Render, EAS — только после ок Никиты.

## План (утверждён 15 октября)

| Этап | Что | Статус |
|---|---|---|
| 0 | Ветка, коммиты спецификации и отложенных правок 1.0.11 | готово |
| 1 | Пульт (remote config `onb_main` / `onb_content` / `pw_main` / `pw_after_cancel`), экран 0 (заставка), QA-меню в тестовых сборках, тестовая метка устройства по ссылке, защита Meta/PostHog от тестовых сборок, ATT-ожидание AppsFlyer 180 с | в работе |
| 2 | Онбординг 1–16 (43 артборда), хаптика, карусель, ATT поверх лоадера | — |
| 3 | Пейвол 17–19 (B1–B3, P1 с видео), оффер 20, покупка, restore; убрать клиентские af_start_trial / af_subscribe | — |
| 4 | После покупки 22–25: Success, Save plan, туториал 6 шагов, Payoff | — |
| 5 | Аналитика: события экранов, пробелы, метка sandbox | — |
| 6 | Preview mode: анонимный аккаунт, merge, один бесплатный AI-лог, защита от переустановки | — |
| Финал | Полный прогон, /code-review, чеклист теста на телефоне, черновик настроек Adapty | — |

## Решения по ходу

- 15 окт: тесты O2 (`features: try_it`) и O5 (`ask_name`) — глубокий бэклог, не делаем: на странице V3 экранов нет.
- 15 окт: экран 0 (заставка «иконка оживает») — в этом билде. Полная анимация только на пути в онбординг (ждём конфиг, не дольше 3 с); у вошедших пользователей — статичная заставка без задержки.
- 15 окт: экран 16 и отзыв в лоадере в сборке рабочие, но скрыты (`social_proof.show: false`). Демо-отзывов в бинаре нет: контент только из `onb_content`. Никита включает экран для своего айфона через тестовую метку: секретная ссылка `yumyummy://tester?code=…` пишет код в custom attribute Adapty `qa_tester`, в Adapty аудитория по этому коду получает `show: true` и демо-контент. Код живёт только в Adapty, в приложении секрета нет.
- 15 окт: имя события экрана остаётся `onboarding_screen_viewed` (а не `onb_screen_viewed`), версия онбординга — в свойстве `onboarding_version`, чтобы v1 и V3 считались в одной воронке.
- 15 окт: тестовая сборка = `__DEV__` или `EXPO_PUBLIC_QA_BUILD=1`: AppsFlyer выключен, у событий PostHog super property `qa_build: true`, в Sentry environment `qa`, доступно QA-меню.

## Состояние Adapty (чтение, 15 окт)

- `onb_main` → флоу a8b7ec17 (все). `pw_main` → pw_welmi a31d5e53 (две аудитории). `pw_after_cancel` — аудиторий нет в ответе CLI (тест виден только в дашборде). Legacy `main` и `onboarding` активны.
- CLI 0.9.0 не показывает remote config флоу.

## Этап 1

Код: `mobile/src/config/` (types, defaults, parse, onboardingConfig, paywallArms, qa, testerMark, buildFlags, demoContent), `components/splash/SplashIntro.tsx` (экран 0 + StaticSplash), `app/qa.tsx`, `app/tester.tsx`, `app/(intro)/v3/index.tsx` (заглушка до этапа 2), `app/index.tsx`, `app/_layout.tsx`, `analytics/*`, `billing/adapty.ts`, `app.json` (нативная заставка), `eas.json` (`EXPO_PUBLIC_QA_BUILD: "0"` во всех профилях), `scripts/qa-sim-build.sh`.

Как работает:
- `index.tsx`: вошедшим — StaticSplash (как нативная заставка), без ожидания. Не вошедшим — SplashIntro, параллельно `resolveOnboardingAssignment()` (сохранённый арм или `getFlow(onb_main)` ≤2,5 с). Выход из заставки не раньше 1,5 с и после готовности арма; `onboarding: v1` → `/(intro)` (старый путь), иначе `/(intro)/v3`.
- Купивший без входа (pending purchase) идёт на `/save-plan` и в тест онбординга не попадает. Кто был посреди старого онбординга при обновлении (есть draft, нет арма) — закрепляется на v1 (`default_reason: pre_v3_draft`).
- PostHog: super props и person props `onboarding_version`, `onb_config_source`, `onb_variation_id`, `onb_variation_name`, `onb_ab_test`; событие `onboarding_config_assigned` (с `fetch_ms`, `default_reason`).
- Парсер пейвол-армов: `render` → иначе `use_native` = наш экран → иначе флоу с view → иначе наш экран.
- Тестовая метка: `yumyummy://tester?code=…` → Adapty `qa_tester=<code>`, PostHog `qa_tester: true` (без кода); метка переписывается после identify и logout.

Ревью субагентом (15 окт): исправлено — OTA-риск `.env.local` (флаги QA только через окружение скрипта сборки, кэш Metro сбрасывается до и после), маршрут по эффективному конфигу (QA-переопределения), загрузка QA-переопределений на старте, гонка метки с identify, сброс арма во время запроса (счётчик поколений), страховки заставки, `qa_build` пишется и как false, вложенная чистка переопределений. Проверено `expo export --clear`: в production-бандле (QA=0 и без переменной) демо-контента нет.

Отложено в этапы:
- Этап 2/4: сбрасывать сохранённый арм по завершении онбординга (после входа на Save plan), super props оставить.
- Этап 3: `resolvePaywallArm` ждать `waitForAdaptyIdentify()` перед getFlow (как `paywall.tsx`).
- QA-кнопка не видна поверх нативных full-screen модалок (пейвол, save-plan) — открывать меню до них.

**Перед любым `eas update` / `expo export` на этом Маке: только с `--clear`** (Metro не учитывает переменные окружения в кэше).

**До релиза в Adapty:** арм(ы) `onb_main` без ключа `onboarding` = V3 по умолчанию. Если нужен старый онбординг как контроль T0 — явный `"onboarding": "v1"`. Проверить, что билды ≤1.0.10 видят на `onb_main` (флоу с view без `use_native` они рендерят).

## Открытые вопросы

- Проверить 412 kcal Joe & The Juice и источник фразы про 80% (экран 12) — этап 2.
- AppsFlyer: что с установкой, если приложение закрыли до ATT — тест на телефоне с `isDebug`.
