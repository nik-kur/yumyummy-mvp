# Реестр: что меняется через Adapty без новой сборки

Живой документ. Сюда попадает каждый ключ, текст, переключатель и слот, которыми приложение управляется из Adapty. При добавлении нового ключа в код запись добавляется сюда в том же коммите. Код: `mobile/src/config/` (`types.ts` — все ключи, `defaults.ts` — значения по умолчанию, `parse.ts` — как читаются).

Сборка: 1.0.11 (ветка `onboarding-v3`). Старые версии (≤ 1.0.10) читают из всего этого только `use_native`.

## Как это устроено

- **Плейсмент** — место в приложении (онбординг, пейвол, оффер). В Adapty: Placements.
- **Арм** — вариант A/B теста на плейсменте. Каждый арм — флоу, у флоу есть **Remote config** (JSON). Приложение читает его и решает, что показать.
- **Значения по умолчанию.** Если ключа нет, значение кривое или Adapty не ответил вовремя (3 с для онбординга, 5 с для пейвола), приложение берёт значение по умолчанию. По умолчанию всё в безопасном для ревью Apple виде. Ошибка в одном ключе не ломает остальные.
- **Закрепление.** Арм онбординга запоминается на устройстве при первом запуске. Смена конфига действует на новые установки; у уже начавших остаётся их вариант.
- **Где менять:** Adapty → Placements → плейсмент → флоу арма → Remote config (язык `en`) → вставить JSON → Save → Publish.
- **Проверить до живых пользователей:** тестовая метка на своём телефоне (ссылка `yumyummy://tester?code=…` → аудитория по атрибуту `qa_tester`) или QA-меню в тестовой сборке. В QA-меню есть все ключи ниже.

## Правила (договорённость с Никитой)

- Любые изменения в Adapty — только с ок Никиты. Claude готовит план с точными значениями.
- Никогда `adapty placements update --audiences` на плейсменте с A/B тестом: команда стирает армы теста.
- Идущий тест на `pw_after_cancel` не трогать.
- Ключи только добавляются и никогда не переименовываются: старые сборки должны продолжать работать.
- Перед отправкой сборки на ревью Apple — чеклист в конце файла.

## Плейсменты

| Плейсмент | Что | Есть в Adapty? |
|---|---|---|
| `onb_main` | Онбординг: тесты и переключатели | есть (флоу a8b7ec17) |
| `onb_content` | Тексты, цифры, отзывы для всех армов (без A/B) | **нет, создать (с ок)** |
| `onb_welcome` | Слот: экран из Adapty вместо Welcome | нет, создаётся под тест |
| `onb_social` | Слот: экран из Adapty вместо экрана 16 (отзывы) | нет, создаётся под тест |
| `pw_main` | Пейвол 17–19 | есть (идёт тест native-monthly vs pw_welmi) |
| `pw_after_cancel` | Оффер после отмены покупки (20) | есть (идёт тест pw_offer_price vs pw_offer_free) |
| `main`, `onboarding` | Старые плейсменты для ≤ 1.0.10 и для `render: "legacy"` | есть, не трогаем |

## `onb_main` — онбординг

| Ключ | Значения | По умолчанию | Что меняет | Тест |
|---|---|---|---|---|
| `onboarding` | `v3`, `v1` | `v3` | Новый онбординг или старый (контроль) | T0 |
| `welcome.variant` | `A`, `B`, `C`, `D` | `A` | Экран 1: A фото + плашка, B + лавр, C маскот + лавры, D демо-видео | O3 |
| `welcome.render` | `native`, `flow` | `native` | `flow` = экран Welcome из флоу на `onb_welcome` | слот |
| `welcome.headline` | текст или `null` | `null` (как в дизайне) | Заголовок Welcome | |
| `welcome.subline` | текст или `null` | `null` | Подзаголовок Welcome | |
| `features` | `screen`, `off` | `screen` | Показывать экран Features (12) | O1 |
| `social_proof.show` | `true`, `false` | `false` | Экран 16 с отзывами. Выключен, пока нет настоящих отзывов (UK запрещает выдуманные) | |
| `social_proof.hero` | `before_after`, `text` | `before_after` | Верх экрана 16: фото до/после или текст | O4 |
| `social_proof.render` | `native`, `flow` | `native` | `flow` = экран 16 из флоу на `onb_social` | слот |
| `loader_review` | `true`, `false` | `false` | Карточка отзыва в лоадере (14) | |
| `plan` | `chart`, `ahead` | `chart` | Экран плана: график веса или «See what's ahead» с вехами | O7 |
| `att` | `loader`, `welcome` | `loader` | Где спрашиваем разрешение на отслеживание (ATT) | O6 |
| `after_cancel_offer` | `true`, `false` | `true` | Показывать оффер после отмены покупки | C5 |
| `tutorial` | `true`, `false` | `true` | Тур по Today после покупки (заработает в этапе 4) | |
| `free_first_log` | `true`, `false` | `true` | Первый AI-лог бесплатно в preview mode (заработает в этапе 6) | PM2 |
| `use_native` | `true` | — | Только для старых сборок (≤ 1.0.10). Не убирать там, где стоит | |

Пример (контроль + Welcome C + без Features):
```json
{"use_native": true, "onboarding": "v3", "welcome": {"variant": "C"}, "features": "off"}
```

## `onb_content` — тексты, цифры, отзывы

Один конфиг для всех. Пустые поля = тексты из дизайна.

| Ключ | Что | По умолчанию |
|---|---|---|
| `rating` | Рейтинг на экранах («5.0 ★ avg App Store rating», чип «★ 5.0», рейтинг в экранах из Adapty) | `"5.0"` |
| `users` | Число пользователей («12,000+ trackers») | `"12,000+"` |
| `reviews.{lose,gain,maintain,track}` | Отзывы для экрана 16 по цели: `[{"text","name","city"}]` | пусто → экран 16 пропускается |
| `before_after.{lose,gain,maintain,track}` | Фото до/после: `{"before_url","after_url","caption","quote"}` (https-ссылки) | пусто |
| `loader_review.{lose,gain,maintain,track}` | Отзыв в лоадере: `{"text","name","city"}` | пусто |
| `texts` | Замена любого текста по ключу (ниже) | — |

Ключи `texts`:

| Ключ | Экран | Что |
|---|---|---|
| `welcome.headline`, `welcome.subline` | 1 Welcome | Заголовок / подзаголовок (`onb_main` важнее) |
| `reflect.{lose,maintain,gain,track}.before` / `.accent` / `.sub` | 3 Reflect | Начало фразы / выделенная часть / подстрочник по цели |
| `proof.body` | 8 Proof 2× | Текст под графиком |
| `features.{yes,yes_accuracy,yes_gave_up,yes_eating_out,yes_other,no,no_same,no_up}.claim` | 12 Features | Строка-утверждение (вариант зависит от ответов про опыт и барьеры) |
| `plan.guide_title`, `plan.guide_sub` | 15 Plan | Плашка про первые 7 дней |

Пример:
```json
{"rating": "4.9", "texts": {"plan.guide_title": "Your 7-day kickstart is ready"}}
```

## `pw_main` — пейвол 17–19

| Ключ | Значения | По умолчанию | Что меняет |
|---|---|---|---|
| `render` | `native`, `flow`, `legacy` | без ключа: есть `use_native` → `native`; иначе флоу с экраном → `flow` | Наш V3 / экраны флоу Adapty / старый пейвол из `main`. Если у `native`-арма нет продуктов, показывается старый пейвол |
| `variant` | `b3_joe`, `b3_home`, `b3_office`, `b3_wide`, `p1_photo`, `p1_text`, `p1_voice` | `b3_joe` | b3_*: B1 → B2 → B3 с фото; p1_*: видео в айфоне → B2 → светлые тарифы |
| `price_emphasis` | `billed`, `design`, `weekly` | `billed` | Какая цена крупно. `billed` — сумма списания + строка «3 days free, then …» (безопасно для ревью); `design` — как на макете (£4.17 /mo); `weekly` — цена за неделю (£0.96 /wk) |
| `show_rating` | `true`, `false` | `true` | Лавры «5.0 ★ avg App Store rating» на B3 и чип «★» на светлых тарифах |
| `copy.b1_title`, `copy.b1_today`, `copy.b1_cta` | текст | дизайн | B1: заголовок, строка «Today», кнопка |
| `copy.b2_title`, `copy.b2_cta` | текст | дизайн | B2 (напоминание) |
| `copy.p1_title`, `copy.p1_cta` | текст | дизайн | P1 (видео) |
| `copy.plans_title`, `copy.plans_today`, `copy.plans_cta` | текст | дизайн | Экран тарифов |
| `use_native` | `true` | — | Только для старых сборок: без него ≤ 1.0.10 покажут флоу |

Тарифы — это продукты на флоу арма в Adapty: 1–3 карточки, годовой выбран по умолчанию, «SAVE N%» считается сам. Цены и триал берутся из App Store. Тесты цен и триала — продуктами на флоу, без сборки. B1/P1/B2 показываются только если у человека есть триал; из Profile и у вошедших сразу тарифы.

Пример (вариант как на макете, без рейтинга):
```json
{"use_native": true, "render": "native", "variant": "b3_home", "price_emphasis": "design", "show_rating": false}
```

## `pw_after_cancel` — оффер 20

| Ключ | Значения | По умолчанию | Что меняет |
|---|---|---|---|
| `render` | `native`, `flow` | без ключа: флоу с экраном → `flow` | Наш оффер или экран флоу Adapty (сейчас идёт тест флоу Adapty) |
| `variant` | `costa`, `closeup` | `costa` | Фото: Costa или курица с рисом + плашка |
| `price_emphasis` | `billed`, `design` | `billed` | `billed` — крупно «£4.99 / week»; иначе «Try it FREE» |
| `copy.headline` | текст | «Try it FREE» | Крупный заголовок (например «50% OFF»; работает при `design`) |
| `copy.badge`, `copy.cta`, `copy.footnote` | текст | «Last offer», «Continue», «No commitment · Cancel anytime» | Плашка, кнопка, подпись |

Продукт — первый продукт с триалом на флоу арма. Если триала у человека нет (уже был), оффер не показывается. Это касается и экранов флоу Adapty.

## Слоты: экран из Adapty вместо нашего

| Где | Включается | Плейсмент |
|---|---|---|
| Welcome (1) | `onb_main`: `"welcome": {"render": "flow"}` | `onb_welcome` |
| Отзывы (16) | `onb_main`: `"social_proof": {"render": "flow", "show": true}` | `onb_social` |
| Пейвол (17–19) | `pw_main`: `"render": "flow"` | сам `pw_main` |
| Оффер (20) | `pw_after_cancel`: `"render": "flow"` | сам `pw_after_cancel` |

Флоу в слоте может вызывать действия приложения (custom actions, запрос ATT и пушей) и показывать данные человека через custom tags (например, `HERO_LINE`, `TARGET_WEIGHT`, `RATING`). Контракт: `mobile/src/billing/flowBridge.ts`.

## Не через remote config, но тоже в Adapty

- **Продукты на флоу** — цены, планы, триал (см. `pw_main`).
- **Аудитории** — кому какой флоу (тестовая метка `qa_tester`, Apple Search Ads и т.п.).
- **Интеграция с AppsFlyer** — какие события покупок уходят в AppsFlyer; план на день релиза: [purchase-events-appsflyer-2026-10.md](purchase-events-appsflyer-2026-10.md).

## Чеклист перед отправкой на ревью Apple

- `pw_main`: ни один арм не стоит на `design` / `weekly` и не отдаёт флоу Adapty, где крупно цена за месяц. Безопасно: `price_emphasis: "billed"` (или ключа нет).
- `pw_after_cancel`: идущий тест — экраны флоу Adapty; проверить, что на них видна сумма списания.
- `onb_main`: `social_proof.show` и `loader_review` выключены (демо-отзывы ревьюеру не показываем).
- Тексты в `onb_content.texts` без обещаний, которые приложение не выполняет.
