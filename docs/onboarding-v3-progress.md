# Онбординг и пейвол V3: журнал реализации

Спецификация: [knowledge/onboarding-v3-implementation-2026-10.md](knowledge/onboarding-v3-implementation-2026-10.md) (раздел «Договорённости 15 октября» главнее). Дизайн: канвас https://claude.ai/artifact/LxWpJAaF5xDcZmAynawjNM, страница «V3 · правки 14 окт». Локальная копия `design/canvas_backup/project/` (обновлена 15 окт 20:01) побайтно совпадает с живым канвасом на 16 окт: 72 артборда V3, включая экран 0 (`V3_Splash`, `V3_Splash_story`). Картинки канваса (54 blob) скачаны в scratchpad сессии `canvas_live/blobs/` (карта id → файлы `blob_ids.json`); при новом чате скачивать заново через Artifact read с `path` = id.

Ветка: `onboarding-v3` от main. Коммитить в ветку можно без спроса; push, PR, merge, Adapty, Render, EAS — только после ок Никиты.

## План (утверждён 15 октября)

| Этап | Что | Статус |
|---|---|---|
| 0 | Ветка, коммиты спецификации и отложенных правок 1.0.11 | готово |
| 1 | Пульт (remote config `onb_main` / `onb_content` / `pw_main` / `pw_after_cancel`), экран 0 (заставка), QA-меню в тестовых сборках, тестовая метка устройства по ссылке, защита Meta/PostHog от тестовых сборок, ATT-ожидание AppsFlyer 180 с | готово 16 окт |
| 2 | Онбординг 1–16 (43 артборда), хаптика, карусель, ATT поверх лоадера | готово 16 окт |
| 3 | Пейвол 17–19 (B1–B3, P1 с видео), оффер 20, покупка, restore; убрать клиентские af_start_trial / af_subscribe | готово 16 окт |
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
- 17 окт (Никита): плашки Joe & The Juice — розовый смузи «Beets & Berries smoothie 368 kcal» (b3_joe), сэндвич на `b3_wide` «Joe & The Juice Tunacado 506 kcal» (оба по UK-меню на Deliveroo; 412 убрано). Рейтинг «5.0 ★» оставляем.
- 17 окт (Никита): по умолчанию (и для ревью Apple) `price_emphasis: billed` — крупно сумма списания и строка «3 days free, then …» на пейволе и оффере. Вариант как на канвасе (`design`) включается в A/B тесте через Adapty без билда.

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

Прогон в симуляторе (16 окт, iPhone 17e 390×844, Release + `EXPO_PUBLIC_QA_BUILD=1`, скриншоты `docs/onboarding-v3-screens/stage1/`):
- Экран 0 по раскадровке; «Y» анимации совпадает с нативной заставкой до пикселя (рисуется тем же PNG), цвет фона совпадает. Кадры 0–0,3 с с более ярким терракотом — системная анимация открытия иконки, не наш код.
- Конфиг `onb_main` с чистой установки: 1,2 с; повторно 0,3–0,4 с. Первый прогон на свежем симуляторе: >2,5 с (активация Adapty ~2 с) → лимит поднят до 3 с, опоздание пишется в PostHog `onboarding_config_late`.
- Сейчас живой `onb_main` (флоу a8b7ec17, вариант «onb_main») без ключа `onboarding` → V3 по умолчанию, как задумано.
- QA-меню, `onboarding: v1` → старый Welcome, тестовая метка `yumyummy://tester?code=…` (Adapty ок) — работают.
- PostHog: `onboarding_config_assigned` и `qa_tester_marked` с `qa_build: true`, `onb_config_source`, `fetch_ms`.

Отложено в этапы:
- Этап 2/4: сбрасывать сохранённый арм по завершении онбординга (после входа на Save plan), super props оставить.
- Этап 3: `resolvePaywallArm` ждать `waitForAdaptyIdentify()` перед getFlow (как `paywall.tsx`).
- QA-кнопка не видна поверх нативных full-screen модалок (пейвол, save-plan) — открывать меню до них.

**Перед любым `eas update` / `expo export` на этом Маке: только с `--clear`** (Metro не учитывает переменные окружения в кэше).

**До релиза в Adapty:** арм(ы) `onb_main` без ключа `onboarding` = V3 по умолчанию. Если нужен старый онбординг как контроль T0 — явный `"onboarding": "v1"`. Проверить, что билды ≤1.0.10 видят на `onb_main` (флоу с view без `use_native` они рендерят).

## Этап 2

Код: экраны `mobile/src/app/(intro)/v3/` (index = Welcome A–D, goal, reflect, source, gender, age, body, activity, target, goal-check, pace, proof, tracked, barriers, features, loader, plan, social); компоненты `src/components/onb/` (OnbLayout, OnbButton, OptionCard, ChoiceScreen, MascotMessage, Sticker, Wheel, Ruler, PaceSlider, UnitToggle, SvgSpec, SourceLink); логика `src/onb/` (flow.ts — порядок, ветки и прогресс; plan.ts — ИМТ, направление, проверка цели, темп, калории, даты, imperial; buildPlan.ts; useOnbScreen.ts; theme; assets; generated/*). Ассеты: `scripts/v3_assets.py` (из blob-ов канваса → `assets/v3/onb`), графики Features и плана 1:1 из разметки канваса: `scripts/v3_extract.py` → `src/onb/generated/*`. Демо-отзывы и фото только для QA: `src/config/demoContent.ts`, `src/config/demo/`.

Решения по ходу (не было на канвасе / уточнено):
- Целевой вес спрашиваем при любой цели (Miro «Логика цели»); план по направлению веса: lose / zone / gain / recomp (набор мышц при том же весе) / cut (набор мышц, вес вниз — график как у похудения). Цель «похудеть» с целевым весом выше текущего ведётся как набор (экрана «переключиться на набор?» в V3 нет).
- Проверка цели показывается, когда вес меняется >1 кг, и всегда, если цель ниже ИМТ 18,5. Здоровый вес округляется вверх до целого кг (как «51 kg» на канвасе).
- Темп: похудение 0,1–0,9 кг/нед (рекомендовано 0,5 — ровно посередине, как на канвасе), набор 0,1–0,4 (0,25). Калории не ниже пола (жен. 1200, муж. 1500, другое 1350, не ниже BMR); если пол съедает дефицит — план как поддержание.
- Тексты, которых нет на канвасе (мои, правятся через `onb_content.texts` или по запросу): подписи темпа «Easy to stick with.» / «Fast, so it takes more discipline.»; карточки ИМТ ≥25 «A healthier weight than today» и «Above the healthy range for your height»; набор «Gaining X kg is a realistic target / is ambitious»; план «ahead» без «by New Year» (дата любая).
- Proof 2× один для всех целей (на канвасе один экран).
- Окно оценки App Store появляется само через 2 с на экране 16 (в iOS нельзя узнать момент его закрытия, поэтому не по Continue).
- Экран 16 пропускается, если `show: false` или для цели нет отзывов в `onb_content`. Карточка отзыва в лоадере — только при `loader_review: true` и наличии отзыва.
- Лоадер: 5,2 с после ответа на ATT, 4 строки с числами человека.
- На маленьких экранах контент прокручивается (иначе не помещается Source и др.).
- Пол «Other»: BMR по середине формулы; в Telegram-боте (`app/bot/onboarding.py:141`) «не male» считается female — бэкенд-задача на потом.

Ревью субагентом (16 окт): исправлено — лоадер мог зависать/сбрасываться при смене конфига, пол калорий мог дать профицит при «похудении», колесо сохраняло значение только по остановке, проверка ИМТ пропускалась при неподвижном весе, экран проверки цели менял текст при выходе, линейка одним огромным SVG (теперь куски по 60 делений), прокрутка на маленьких экранах, локальная дата вместо UTC, person properties для пола/возраста/направления, сброс pain_points, аналитика ATT на Welcome, disabled-состояние кнопки. Сам нашёл в симуляторе: барабан/линейка останавливались между значениями (добавлена доводка), обрезка тени карточек, иконка ссылки на источник выпадала, фото до/после кадрировались не так, окно оценки открывалось поверх пейвола, экраны на долю секунды видели дефолтные ответы до чтения из памяти (теперь ждут).

Прогон (iPhone 17e 390×844): все экраны сверены с рендерами артбордов — листы `docs/onboarding-v3-screens/stage2/`. Ветки: lose / ambitious / BMI<18.5 / gain / recomp / maintain / track; Welcome A–D; Features yes и no_same; план chart (4 режима) и ahead; лоадер с ATT и с отзывом; экран 16 с демо и окно оценки; imperial (ft/in, st/lb). PostHog: `onboarding_screen_viewed` по всем экранам с вариантами.

QA-меню: заготовки ответов + прыжок на любой экран, сценарии одним нажатием (Welcome B/C/D, Loader + review, Plan ahead, Social demo / text hero).

Не проверено/отложено: VoiceOver для барабанов/линейки/ползунка (нет adjustable-ролей); проверка на реальном iPhone (хаптика в симуляторе не ощущается); экраны на 667 pt по высоте — на этапе финального прогона.

## Этап 3

Код: `mobile/src/app/paywall.tsx` (оркестратор), `src/components/pw/` (V3Paywall — шаги; V3Screens — B1, B2, B3, P1, светлые планы; OfferScreen — 20; PlanCards, PhotoStage, PwParts, copy.ts — тексты, фото и плашки), `src/billing/v3Pricing.ts` (цены, триал, «SAVE N%»), ассеты `assets/v3/pw` (`scripts/v3_assets.py`).

Как работает:
- Арм `pw_main` решает рендер: `native` → наш V3 (b3_* : B1 → B2 → B3; p1_* : P1 → B2 → светлые планы), `flow` → экраны флоу Adapty, `legacy` → старый кодовый пейвол с `main`. Наш V3 покупает продукты флоу арма (`getPaywallProducts(flow)`) и логирует показ на нём (`logShowFlow`) — кодовые и билдерные армы в одном A/B тесте. Карточек столько, сколько продуктов (1–3; три светлые — столбиком).
- B1/P1/B2 только при триале: нет триала у человека, вход из Profile или из входа в аккаунт → сразу планы. На B2 системный запрос пушей через 0,6 с (или по кнопке, если она нажата раньше); напоминание о конце триала ставится на «за день до списания» по длине триала продукта.
- Нет продуктов у арма при живом Adapty → старый пейвол (не тупик) + событие в Sentry. Adapty не ответил → V3 по умолчанию с кнопкой «Try again» вместо карточек.
- Оффер 20: арм `pw_after_cancel`, предзагрузка при показе пейвола, показ после отмены App Store, один раз за визит, поверх пейвола (крестик возвращает на тот же шаг — планы). Показывается только если у человека есть триал на продукте оффера (и для билдерных офферов тоже). Выключатель `after_cancel_offer` в `onb_main`.
- Текущие армы: `pw_offer_price` / `pw_offer_free` без remote config → в новой сборке остаются экранами флоу Adapty (идущий тест не меняется). `pw_main`: контроль 482e6945 (`use_native`) в новой сборке = наш V3 b3_joe с продуктами этого флоу; pw_welmi = флоу Adapty.
- Тексты переопределяются ключами `copy` арма: b1_title, b1_today, b1_cta, b2_title, b2_cta, p1_title, p1_cta, plans_title, plans_today, plans_cta; оффер: badge, headline, cta, footnote. `price_emphasis: billed` — крупно сумма списания (B3: «£49.99 /yr», строка «3 days free, then …»; оффер: «£4.99 / week», «after 3 days free»).
- Заголовок B1 / светлых планов по плану: lose/cut/gain «Reach {вес} by {дата}.», recomp «Build muscle at {вес}.», maintain «Feel better while you keep your shape.», track «Know what you eat, choose better.» + «Start for free today.» (без триала «Start today.»).
- Клиентские `af_start_trial` / `af_subscribe` убраны (перенос в серверную интеграцию Adapty → AppsFlyer, нужен ок).
- QA: `/paywall?qa_offer=1` и кнопки «→ Paywall», «→ Offer» в QA-меню; `mock_purchase` пропускает StoreKit.

Ревью субагентом (16 окт): исправлено — после закрытия оффера пейвол начинался с B1 (теперь оффер поверх), тупик при арме без продуктов, три светлые карточки в ряд не помещались, плашка `b3_wide` налезала на заголовок на 667 pt, периоды «3 months» писались как «month», пуш мог потеряться при двойном тапе, оффер «free» показывался без права на триал (и у билдерных), покупки билдерного оффера писались как главный пейвол, повторная загрузка не перезапрашивала оффер, поздний оффер после покупки. Сам нашёл в симуляторе: «US$4.17» рядом с «$49.99» (цена в месяц теперь в формате магазина), домен в плашке переносился посреди слова, форма бейджа «1» на B2, заголовок P1 в 3 строки (теперь ужимается до двух, как на канвасе), «50% OFF» зря уменьшался. Флоу Adapty получали `RATING: '4.9'`, теперь то же число, что на наших экранах.

Прогон (16 окт, iPhone 17e 390×844, витрина симулятора US — цены в $): листы `docs/onboarding-v3-screens/stage3/`. Проверено: живой `pw_main` без QA → флоу pw_welmi (экраны Adapty); `render: native` → B1 → B2 (системный запрос пушей) → B3 с настоящими продуктами флоу; «Continue» → окно App Store (вход в Apple-аккаунт не делал, «Отменить») → оффер 20 поверх → ✕ → снова B3; b3_home / office / wide; P1 photo / text / voice (видео играет) → B2 → светлые планы, выбор месячного; оффер costa / closeup / «50% OFF» / billed; `price_emphasis: billed` на B3; вход из Profile (`dismissable`) сразу на планы с крестиком; `render: legacy` → старый пейвол. Не проверено: покупка до конца (нужен sandbox на телефоне), вход уже вошедшего пользователя, экран 667 pt.

## Открытые вопросы

- 16 окт (Никита): фраза «80% of users… maintain their weight loss» без источника заменена на «In a 6-month study of 142 adults, the people who logged their meals most often lost the most weight.» — Harvey et al., Log Often, Lose More, Obesity 2019 (PMID 30801989); `features.tsx` CLAIM_OVERRIDES.
- AppsFlyer: триалы и покупки только с сервера Adapty (trial_started / subscription_started, поле Sandbox пустое) — Никита решает 17 окт; до релиза включить в Adapty. После входа приложение сразу заново передаёт `appsflyer_id` в Adapty (`state/auth.tsx`).
- AppsFlyer: что с установкой, если приложение закрыли до ATT — тест на телефоне с `isDebug`.
