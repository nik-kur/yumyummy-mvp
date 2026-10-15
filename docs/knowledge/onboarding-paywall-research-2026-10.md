# Onboarding & paywall: что мы знаем (исследование 1 октября 2026)

Источник: папка `/Users/nikita/Documents/YumYummy/YumYummy Onboarding & Paywall/` (полный отчёт `report/index.html`, онлайн https://claude.ai/artifact/4Q3gST5GN8SJeph7jKBpny, записи 12 приложений `data/<slug>/`, заметки по 55 видео `research/yt_*.md`, бенчмарки с URL `research/benchmarks.md`). Этот файл — выжимка для контекста; за экранами и цитатами идти в отчёт.

## Решения

- 2026-10-01: волна 1 = H1–H5 (цена на экране до Apple-листа, 3-шаговая trial-подводка, оффер после отмены как фикс, 2 плана, заголовок из квиза). Yearly = новый план $49.99 (одобрен Apple), старый $89.99 не используем; арм £29.99 отложен. Nutracheck не углубляем. ScreensDesign-аллованс можно тратить.
- 2026-10-02: порядок работ: (1) мокапы новых пейволов → выбор → сборка в Adapty и A/B против текущего S_hero (weekly с 3-дневным триалом как контроль), (2) purchase-cancelled flow включить как фикс, (3) потом онбординг. Триал оставляем и на monthly, и на yearly (Никита не хочет триал только на год).

## TL;DR

- Квиз не течёт. 71–75% установок доходят до пейвола за ~90 секунд: это выше, чем у всех конкурентов по времени (у них 2–8 минут) и на уровне ориентира «80%+ хорошо» (Superwall, Mobbin). Онбординг нужно улучшать, но не он даёт 2,7%.
- Течёт шаг после тапа. 32% нажимают «Start my 3-day free trial», затем 84% отменяют Apple-лист. В рынке завершение начатой покупки ≈50% (Superwall) и 63% у Cal AI; у нас 12%. За 6 недель: 190 показов → 58 тапов → 45 отмен → 17 покупок; за последние 2 недели (Meta-трафик) 24 тапа → 4 покупки.
- Причина, которую видно без тестов: живой пейвол (S_hero_v1) не показывает цену. Она есть только в юридической строке 12 px. Apple-лист становится первым местом, где человек читает «£9.99 в месяц» или «£4.99 в неделю». Оба арма A/B провалились одинаково (monthly 0 из 10, weekly 2 из 14 в GB).
- Второго шанса нет: hard paywall без крестика, оффер после отмены (pw_after_cancel) выключен. У 9 из 11 конкурентов стена мягкая и есть лестница офферов; у двух «жёстких» (Cal AI, Welmi) цена показана на шаге выбора плана до Apple-листа.
- Что общего у всех: dated plan reveal («50 кг к 30 декабря»), yearly по умолчанию (10 из 11), цена в формате «в месяц», вопрос «откуда узнали» (7 из 11), reinforcement между вопросами (8 из 11), имя (7 из 11). У нас из этого есть только plan reveal.
- Волна 1 (пейвол, всё в Adapty без релиза): цена на экране до Apple-листа, 3-шаговая trial-подводка (Cal AI / Welmi / Lose It), включить оффер после отмены, 2 плана (новый yearly $49.99, одобрен Apple, по умолчанию + monthly), заголовок из квиза. Волна 2: онбординг (эхо рекламы на welcome, reflect-back экраны, имя, source question). Волна 3: alignment по углу рекламы.

## Наша воронка (PostHog, 20 сен – 1 окт 2026)

| Шаг | Польз. | от пред. | от S1 |
|---|---|---|---|
| S1 Welcome | 110 |  | 100% |
| S2 Goal | 96 | 87% | 87% |
| S3 Why (2× stat) | 89 | 93% | 81% |
| S4 Gender | 89 | 100% | 81% |
| S5 Age | 89 | 100% | 81% |
| S6 Height & weight | 87 | 98% | 79% |
| S7 Activity | 82 | 94% | 75% |
| S8 Pain points | 82 | 100% | 75% |
| S9 Calories in vs out | 82 | 100% | 75% |
| S10 So we built both | 81 | 99% | 74% |
| N1 Target & pace (только lose/gain) | 73 |  | 66% |
| N2 Loader | 79 | 98% | 72% |
| N3 Plan reveal | 79 | 100% | 72% |
| Paywall shown | 78 | 99% | 71% |
| Plan tapped (CTA) | 25 | 32% | 23% |
| StoreKit cancelled | 21 | 84% тапов | 19% |
| Purchase success (trial) | 3 | 12% тапов | 2.7% |

По продукту (A/B S_hero_v1): Monthly £9.99 (арм M_single_trial), GB: 10 тапов / 10 отмен / 0 покупок; Weekly £4.99 (арм W_single_trial), GB: 14 тапов / 10 отмен / 2 покупок; Прочие страны (NL, KZ): 3 тапов / 1 отмен / 3 покупок

Динамика: 18 авг – 1 окт (6 недель): показов 190, тапов 58, отмен 45, покупок 17 (tap 31%, tap→buy 29%, view→buy 8.9%); 21 сен – 1 окт (2 недели, Meta): показов 72, тапов 24, отмен 19, покупок 4 (tap 33%, tap→buy 17%, view→buy 5.6%)

### Диагноз

- До пейвола теряем 29%, и почти всё это два места: первый тап на welcome (−13%, там же ATT-промпт в 1.0.10) и ввод роста/веса + активности (−6%). Остальные экраны держат 98–100%. Это нормальная картина для 13 экранов; у конкурентов до пейвола 19–104 экрана.
- После пейвола: 32% тапают CTA (Cal AI 57%), но завершают покупку 12% тапнувших. Опубликованная норма завершения начатой покупки ≈50% (Superwall) и 63% у Cal AI. Если бы мы завершали половину, install → trial был бы ~11% при той же воронке до тапа (0.71 × 0.32 × 0.5).
- Пейвол S_hero_v1 строился как «один план без карточки цены»: заголовок, hero с датой цели, лавры, цитата, таймлайн, CTA. Цена только в terms-строке 12 px. Человек нажимает «Start my 3-day free trial», видит на Apple-листе «3-day free trial, then £9.99/month» и уходит. Это единственный пейвол из 13, где цена не показана крупно до системного листа.
- Цена сама по себе тоже высокая для холодного трафика: £9.99/мес ≈ £120/год при том, что лидер категории продаёт год за $29.99 (Cal AI), BitePal за $35.99, Lose It за $39.99. Наш yearly-продукт в сторе стоит $89.99 и в живом пейволе не предлагается.
- Оффер после отмены (weekly £2.99 с триалом) существует в Adapty и выключен. 21 отменивший за 12 дней не увидел ничего. У Yazio/Foodvisor/MyNetDiary отказ ведёт на второй оффер, у Lifesum/Cronometer на бесплатный режим с повторным пейволом.
- Качество трафика тоже участвует: tap→purchase упал с ~30% (ASA-период, август) до ~17% в Meta-недели. Но даже 30% × 32% × 75% = 7% install→trial, то есть пейвол и был узким местом до Meta.

### Бенчмарки

| Метрика | Мы | Ориентир | Источник |
|---|---|---|---|
| install → paywall | 71–75% | ≥85% рекомендация Superwall; Cal AI 87%; средний по платформе Superwall 56% (2022) | benchmarks.md A1–A3 |
| paywall → начало покупки (тап по CTA) | 32% | Cal AI 57% (Superwall case study); «>40% здорово, <20% разбираться» (эвристика) | benchmarks.md B4, B11 |
| начатая покупка → завершение (Apple-лист) | 12% | ≈50% (Superwall), 63% Cal AI | benchmarks.md B5–B6 |
| install → trial | 2.7% | H&F медиана 6.9%, топ-10% >23% (RevenueCat 2026); Западная Европа 5.0%; Adapty H&F weekly-с-триалом 9.5%, глобально 10.9%; спикеры: 3–7% рынок, 10–15% цель | benchmarks.md C1–C6; yt_pricing_benchmarks |
| trial → paid | н/д (3 триала) | H&F 37.7% (RevenueCat), 35.0% (Adapty); Западная Европа 29.7%; триал ≤4 дней 25.5% vs 5–9 дней 37.4%; annual + ≤4 дня 24% vs 44.6% при 17–32 днях | benchmarks.md E1–E3, F1, F4 |
| install → paid | н/д | H&F D35 2.9%; hard-paywall апы медиана 10.7%, пол 4.2%; из нашего 2.7% триалов получится ~0.7–1.0% | benchmarks.md D1–D3 |
| Планы в H&F | live: только monthly или weekly | 68% подписок и 59–61% выручки H&F на annual; медианы H&F monthly $9.99, weekly $4.99, yearly ~$34.80 (все категории) | benchmarks.md H1–H3, H9 |
| Cal AI (Superwall case study) | — | 87% видят пейвол, 57% начинают покупку, 63% завершают; 123 эксперимента, 61 на onboarding-пейволе; sign-in в конец онбординга = главный фикс drop-off; лишние вопросы в квизе подняли конверсию даже без использования | benchmarks.md I2–I3 |

## Онбординг: сравнение конкурентов

| Приложение | $/мес (оценка) | Экранов до PW | Время до PW | Вопросов | Sign-up | «Откуда узнали» | Имя | Plan reveal с датой | Reinforcement | ATT |
|---|---|---|---|---|---|---|---|---|---|---|
| YumYummy (мы) | — | 13 | ~90 s | 7 | нет | нет | нет | да (N3) | нет | welcome, cold |
| Cal AI | 1.75M | 40 | 182 s | 13 | до PW (Apple/Google/magic link) | Q3 + «tried other apps» Q4 | нет | да («7 kg by May 24») | proof-экран каждые 3–4 вопроса | над лоадером, cold |
| BitePal | 450K | 53 | 239 s | 19 | после покупки | Q1 + Q4 | нет (имя енота) | да + «Commit to my goal» | енот, факты с источником, отзывы в лоадере | 1-й экран, cold |
| Welmi | 250K | 24 | 122 s | 12 | нет | нет | нет | да («See what's ahead») | «why we ask» под вопросами, эхо-лоадер | 2-й экран, cold |
| YAZIO | 5M | 86 | 260 s | 42 | после PW | Q2 + «which app» Q15 | да (6 экранов) | да (заголовок PW) | 16 mascot-интерстишлов, press-and-hold | home, cold |
| MyFitnessPal | 12M | 23 | 132 s | 11 | до квиза + email после | optional после аккаунта | да (Q1) | да (текст) | 4 interstitial + экран-эмпатия | нет в записи |
| Lose It! | 1M | 84 | 222 s | 42 | до PW («Save my program») | нет («counted before?») | нет | да (PROGRAM card) | ~12 «Great!» + накапливающаяся карточка | 2-й экран, cold |
| MyNetDiary | 1.25M | 41 | 182 s | 16 | нет | нет | нет | да (pace slider с датой) | почти после каждого ответа | на Q1, cold |
| Cronometer | 1.25M | 19 | 125 s | 7 | до PW (email+пароль+verify) | нет | да (аккаунт) | текст без графика | нет | после PW, cold |
| FatSecret | 50K | 36 (PW внутри фич) | 203 s | 11 | после plan reveal (3 экрана) | нет | да (Q1) | да, до регистрации | 1 строка | нет в записи |
| Lifesum | 850K | 30 | 121 s | 12 | до PW (обязательно) | Q4 | да (аккаунт) | да (имя + дата) | 1 pop-up | после PW, cold |
| Foodvisor | 1.75M | 86 | 325 s | 42 | стена на 98 s | Q3 + «tried before» | да | да, 4 раза, дата сдвигается | pop-up «program updated», научные лоадеры | 1-й экран, cold |
| Noom | 500K | 104 | 460 s | 53 | на 36 s | Q48 | да (в шапке везде) | да, 4 раза, дата сдвигается | карточки между ответами, trivia | 3 s, cold |
| Nutracheck (UK) | ? | ? | ? | ~9 | email в конце | ? | ? | цель + дата (вывод) | ? | ? |

**Что общего**

- Dated plan reveal у 12 из 12: «цель X кг к дате». У 4 (Foodvisor, Noom, Lose It, MyNetDiary) дата живая и улучшается по ходу квиза. У нас дата есть на N3 и в hero пейвола, но только для lose/gain и без графика.
- Структура «спроси → верни ценность → спроси»: proof-экраны (Cal AI), mascot-интерстишлы (Yazio), «Great!» (Lose It), reinforcement после ответа (MyNetDiary), pop-up «plan updated» (Foodvisor). У нас между вопросами ничего, только три лекции (S3, S9, S10).
- «Откуда узнали» в первых 4 вопросах у 5 из 11 (Cal AI Q3, BitePal Q1, Yazio Q2, Lifesum Q4, Foodvisor Q3); «пробовали другие приложения / считали калории раньше» у 6.
- Имя спрашивают 7 из 11 и используют в plan reveal и/или заголовке пейвола (Yazio, Noom, MFP, Lifesum, Cronometer).
- Target weight + pace slider с живой датой и BMI-фидбеком: Cal AI, MyNetDiary, Welmi, BitePal, Noom, Foodvisor, Lose It.
- ATT почти у всех холодный и ранний (1–3-й экран). Это норма категории; Hannah Parvaz: ATT первым «удваивает opt-in».
- Sign-up до пейвола у 8 из 11 (включая Cal AI). Все YouTube-практики называют это ошибкой; у нас sign-up нет, и это правильно.

**Что различается**

- Длина: 19 экранов (Cronometer) против 104 (Noom). Короткие (Cronometer, Lifesum, Welmi, MFP, 120–130 s) и длинные (Yazio, Foodvisor, Lose It, Noom, 220–460 s) живут в одной категории с сопоставимой выручкой; длина не объясняет выручку.
- Где показывают продукт: Cal AI и Welmi показывают AI-скан только мокапом на welcome/пейволе, Lifesum тремя слайдами после регистрации, Yazio и Lose It вообще не показывают фото-лог до пейвола. Мы показываем демо на S1 и proof-карточку на S10: это редкость.
- Коммитмент: press-and-hold (Yazio), «Commit to my goal» (BitePal), «Save my program» (Lose It). У остальных нет.
- Rating prompt до пейвола: Cal AI, BitePal, Welmi, Yazio (посреди квиза). Остальные после первого использования.
- Нотификации: warm-up до пейвола с цифрой (MyNetDiary «87% more successful», Cal AI) против холодного промпта на старте (FatSecret, Lifesum, Cronometer, Yazio).

**Что работает**

- Короткий путь к пейволу сам по себе не вредит (у нас 71–75% дохода), но у конкурентов за 2–4 минуты квиза накапливаются доказательства и обязательства, которые потом «продают» на пейволе. У нас пейвол приходит через 90 секунд к человеку, который ещё ничего не вложил.
- Reflect-back и имя — самые дешёвые паттерны с заявленными эффектами (Hannah Parvaz: имя +133% активации, один кейс; Headspace multi-select +10% триалов; Grammarly планы под ответы +20% апгрейдов).
- Лоадер с ротацией отзывов (BitePal, Lose It, MyNetDiary) превращает паузу в social proof; у нас лоадер пустой.
- Source question даёт self-reported атрибуцию там, где Meta не отдаёт user-level данные (у нас af_* доходит до ~10% пользователей). Это нужно нам больше, чем конкурентам.

**Что берём себе**

- Не удлинять квиз ради длины. Добавлять только экраны, которые возвращают ценность: reflect-back после S2 и S8, имя, лоадер с отзывами, plan reveal с графиком и датой для всех целей, экран «You've done the hard part».
- Заменить текстовые лекции S9/S10 на один визуал (us-vs-them) и loss-framing: все live-разборы Superwall начинаются с «слишком много текста».
- Добавить «откуда узнали» и «пробовали другие трекеры» вторым-третьим вопросом; ответы использовать как ветку (бывшим пользователям MFP показывать сравнение, новичкам простоту).
- Stones/lb для UK (Nutracheck), и safety-флаг (беременность, РПП) как trust-сигнал.

## Пейвол: сравнение конкурентов

| Приложение | Стена | Триал | Планы (US) | По умолчанию | Крупная цена | Таймлайн | Proof на PW | Urgency | После отказа |
|---|---|---|---|---|---|---|---|---|---|
| YumYummy (live S_hero) | hard, без X | 3 дня | 1 план: monthly £9.99 или weekly £4.99 (A/B) | единственный | нет (только terms 12 px) | да, 4 шага | лавры + 1 цитата | нет | ничего (оффер после отмены OFF) |
| Cal AI | hard на практике (X не виден) | 3 дня (yearly) | Monthly $9.99 · Yearly $29.99 | yearly | «$29.99 per year ($2.49/mo)» мелко; на пикере $9.99/mo vs $29.99 | да, 3 шага + дата списания | нет | нет | не записано |
| Welmi | hard (почти невидимый X) | 3 дня, тумблер | Monthly $9.99 · Yearly $59.99 | yearly, SAVE 50% | $59.99/year, $5.00/month мелко | да, отдельный экран + reminder-экран | нет | нет | не записано |
| BitePal | soft (X) | 3 дня (yearly) | Yearly $35.99 (зачёркнуто $59.99) · Weekly $3.99 скрыт | yearly, Most popular | $2.99 per month | нет | UK-отзыв Sophie, 4.7, 1M users (ниже сгиба) | зачёркнутая цена | не записано |
| Lose It! | soft (X) | 7 дней | только Yearly $39.99 | единственный | $39.99/yr ($3.33/mo) мелко | да, 4 шага (Day 5 email) | 4.8 (680k), 2 отзыва, FAQ | нет | не записано |
| YAZIO | soft (X) | нет | 12 мес $47.90 (зачёркнуто $95.96) · 3 мес $23.99 | 12 мес | $3.99/month | renewal-таймлайн + «How do I cancel» | нет на пикере | скидка 50% → колесо 75% → баннер −88% с таймером | колесо → $23.90/год → sign-up → free + баннер |
| MyFitnessPal | soft (X) | 30 дней | Premium $79.99/yr · $19.99/mo; Premium+ $99.99 · $24.99 | yearly, Save 67% | $6.67/mo | нет | нет | нет | не записано |
| MyNetDiary | soft (X) | нет на пикере; 7 дней как downsell | 12 мес $59.99 (зачёркнуто $107.88) · 1 мес $8.99 | 12 мес, SAVE 44% | $59.99 + $5/mo | нет | текст («3× the weight of free users») | зачёркнутая цена | после отмены Apple-листа: модалка «Try 7 days free» |
| Cronometer | soft (X) | нет | Annual $59.99 · Monthly $10.99 | annual, Save 55% | $5.00 / Month | нет | нет | нет | free tier, баннер Gold, feature gates |
| FatSecret | soft (X), внутри фич | нет | 12 мес $41.99 (зачёркнуто $59.99) · 3 мес $28.99 · 1 мес $14.99 | 12 мес, Limited Offer | цена за период | нет | 1 строка | Limited Offer | ничего, free app |
| Lifesum | soft (X) | нет (скидка вместо триала) | 1 мес $7.49 · 12 мес $49.99 · 3 мес $14.99 (все зачёркнуты ×2) | 12 мес | цена периода + $/mo мелко | нет | таблица Free/Premium + фото-отзыв | «50% off» баннер | free diary → второй контекстный PW с чат-демо |
| Foodvisor | soft («Not now») | нет (30-day money back) | Yearly $83.99 · Family $119.99 · Monthly $14.99 скрыт | yearly | $6.99 / mo | нет | нет | колесо → −75% $23.99 с таймером 10 мин | колесо → оффер → free + feature locks + карточка −75% |
| Noom | soft (X) | 7 дней | 1 план: $98.99 / 2 мес | единственный | $98.99 ($11.36/week мелко) | блоки PRICE TODAY / PRICE AFTER TRIAL + дата | нет | таймер 15 мин «plan reserved» | не записано |

**Что общего**

- Yearly/12 мес по умолчанию у 10 из 11 (исключение Noom с одним 2-месячным планом). Weekly как видимый план нет ни у кого; BitePal прячет его за «Show more plans». Наш живой пейвол продаёт только monthly или weekly.
- Крупная цена «в месяц» у 7 из 11 (Cal AI, Cronometer, Yazio, Foodvisor, BitePal, MFP, Welmi мелко). Никто не ведёт с «$/wk». Цена показана на экране до Apple-листа у всех 11.
- Trial-подводка в 3 шага «We want you to try X for free» → колокольчик «We'll send you a reminder» → пикер с таймлайном: Cal AI, Welmi, Lose It (один и тот же шаблон). «No Payment Due Now» повторяется на каждом шаге.
- Персонализированный заголовок из квиза у 4: Yazio («hit 50.0 kg by December 30!» слово в слово из plan reveal), Noom («Lose 16 lb by December 31» + отпуск), Lifesum и Cronometer (имя).
- Диапазон year-цены лидеров: $29.99 (Cal AI), $35.99 (BitePal), $39.99 (Lose It), $47.90 (Yazio), $49.99 (Lifesum), $59.99 (Cronometer, MyNetDiary, Welmi), $79.99 (MFP), $83.99 (Foodvisor). Monthly: $7.49–$14.99, медиана ~$9.99.

**Что различается**

- Триал: 3 дня (Cal AI, BitePal, Welmi, мы), 7 дней (Lose It, Noom, MyNetDiary как downsell), 30 дней (MFP), нет триала и скидка вместо него (Yazio, Lifesum, Foodvisor, Cronometer, FatSecret). У «без триала» всегда есть зачёркнутая цена.
- Жёсткость: только Cal AI и Welmi фактически hard; остальные soft с лестницей (Yazio/Foodvisor колесо и таймер, MyNetDiary downsell-триал, Lifesum/Cronometer free tier с повторным пейволом).
- Social proof на пейволе: от нуля (Cal AI, Welmi, Yazio пикер, Noom) до полного набора (Lose It: 4.8/680k, отзывы, FAQ; BitePal: UK-отзыв). Vahe (Superwall): на iOS отзывы бьют таймлайн; Parra: таймлайн всё ещё сильный. Противоречие, тестировать.
- Urgency: Noom таймер без скидки, Yazio/Foodvisor скидочные таймеры, у остальных только бейджи. Colесо фортуны (Yazio, Foodvisor) практики называют риском для доверия и App Review.
- Тумблер триала: только Welmi (OFF по умолчанию). Mobbin сообщает, что Apple с начала 2026 режектит тумблеры; Max (Adapty): 5–10% покупают без триала.

**Что работает**

- Цена видна до системного листа: у всех 11. Наш hero-пейвол единственный, где её нет; это ближайшее объяснение 84% отмен.
- Trial-подводка тремя шагами (Cal AI / Welmi / Lose It): Vahe даёт 20–40% аплифта multi-step против single-step; MealTime +21% trial start на Blinkist-таймлайне. Выигрыш в том, что страх «забуду отменить» снимается до того, как человек видит цену.
- Второй оффер после отказа: MyNetDiary встроил 7-дневный триал именно в отмену Apple-листа (ровно наш случай); Nathan Hudson: ограниченная скидка на 3-й день дала 3× конверсий; Vahe: transaction-abandonment paywall с годовым планом и якорем.
- 2 плана с yearly по умолчанию и «Save X%»: Patrick Fon (третий план «никто не берёт»), Parra («dramatic increase» от 2 планов + явного trial-CTA), Cal AI/Cronometer/Welmi/MyNetDiary так и делают.
- Заголовок из квиза (Yazio): Grammarly +20% апгрейдов от планов под ответы; все 4 агентства в SubHub/RevenueCat говорят одно: outcome-заголовок с цифрой из квиза вместо «Premium».

**Что берём себе**

- Вернуть цену на экран: карточка плана с крупной ценой + строка «3 дня бесплатно, затем £X» + CTA с той же суммой, что на Apple-листе. Это первый тест, не вариант.
- Сделать пейвол 3-шаговым по шаблону Cal AI/Welmi: (1) «We want you to try YumYummy for free» + таймлайн с датой списания, (2) напоминание за день, (3) пикер с 2 планами и отзывами.
- Включить pw_after_cancel и переделать его в transaction-abandonment оффер: год со скидкой + недисконтированный monthly как якорь, без weekly.
- Планы: новый yearly $49.99 (одобрен Apple; UK-цену проверить в App Store Connect, ориентир £39.99–£44.99) по умолчанию в формате «≈£3.50/мес, billed yearly, Save 65%» + monthly £9.99. Weekly оставить только как арм в A/B и мерить 30-дневную выручку на установку, не триалы. Старый yearly $89.99 не использовать.
- Заголовок из квиза: «We'll help you lose 6 kg by 12 December» (Yazio), для maintain «Your zone: 2,100 kcal a day». Реальные отзывы UK с «stone» рядом с CTA.

## Alignment (реклама → welcome → квиз → пейвол): сравнение конкурентов

| Приложение | Что обещает реклама (Meta, UK) | Welcome повторяет рекламу? | Квиз → пейвол | Source question |
|---|---|---|---|---|
| YumYummy | result story «nearly a stone» + type/snap/say за 10 s + «3 days free» | наполовину: демо логинга есть, результата и «3 days free» нет | дата цели в hero; остальное (цель, боли, активность) не используется | нет |
| Cal AI | effortless_logging (172 креатива, 13.9M UK reach), fitness_macros, before/after, founder story | частично: «Calorie tracking made easy» + камера-мокап, хуков нет | сильно до plan reveal (7 kg by May 24), ноль после; home с дефолтами 2000 kcal | Q3 + «tried other apps» + referral code |
| BitePal | weight_loss_result, effortless_logging, «Duolingo for weight loss», енот | енот да, результат нет | plan reveal + «Commit», пейвол общий | Q1 |
| Welmi | fitness_macros (мужские UGC), «losing belly fat», effortless | нет; AI-скан впервые на пейволе; квиз только про похудение | дата цели и kcal до пейвола, hero generic кроме даты списания | нет |
| YAZIO | effortless logging (52 UK ads), AI food scan | нет («85 million happy users»); AI Camera после пейвола | цель+дата слово в слово в заголовок пейвола | Q2 + «which app» |
| MyFitnessPal | effortless logging, макросы/белок, meal planning; офферов нет | эхо «it's easy», scan/voice не показаны | reveal (1,420 kcal, дата) не доходит до пейвола; вопросы про meal planning готовят Premium+ | optional после аккаунта |
| Lose It! | no Meta data | 3 пункта без фото/AI | PROGRAM card накапливается, пейвол generic | нет |
| MyNetDiary | competitor switch («vs old trackers»), AI-scan UGC, GLP-1/protein | generic («Top-Rated… 27M users») | reveal сильный, пейвол generic | нет |
| Cronometer | ai_wow_accuracy, photo logging, free trial в 73 креативах | нет; ни AI, ни trial до пейвола | только имя «Hi Julia» | нет |
| Lifesum | no Meta data | эмоциональный welcome без обещания | имя в reveal и заголовке; дата только на reveal | Q4 |
| Foodvisor | no Meta data | «Personalized nutrition», фото после пейвола | имя + дата 4 раза, пейвол generic | Q3 + «tried before» |
| Noom | no Meta data | lifestyle, без еды | имя, вес, отпуск, дата в hero пейвола | Q48 |
| Nutracheck | effortless logging (5.8M UK reach), «I lost 2 stone», eat what you want | store: UK database, awards; историй похудения нет | цель + дата (вывод) | ? |

**Что общего**

- Почти никто не повторяет рекламное обещание на первом экране. Cal AI ближе всех («made easy»), BitePal повторяет персонажа, не результат. Это общая слабость категории и свободное поле.
- Персонализация у всех живёт в plan reveal и обрывается перед пейволом; довели до заголовка пейвола только Yazio и Noom (цель + дата) и Lifesum/Cronometer (имя).
- Source question есть у 7 из 11 и у всех крупных AI-трекеров (Cal AI, BitePal, Yazio, Foodvisor) стоит в первых 3 вопросах. Это их замена user-level атрибуции.
- Welmi и Cal AI, у которых топ-угол рекламы fitness_macros / effortless, спрашивают в квизе только про похудение; разрыв между углом рекламы и флоу встречается даже у лидеров.

**Что различается**

- Длина квиза по источнику: Sociaal (Superwall) даёт «тёплому» трафику из рекламы длинный квиз, прямым заходам короткий. Никто из 12 так не делает (кроме, возможно, Noom с веб-воронкой).
- Lose It и Cal AI ветвят reinforcement по ответу «как считал раньше» («This will be easier than taking notes»). Это единственный пример связки ответ → аргумент.
- Welltory (Superwall): не повторять проблему из рекламы, сразу делать смелое частичное обещание (первый CTA = синк здоровья, 90%). Hannah Parvaz: ~20% не открывают приложение после установки, первый экран должен напомнить «кто мы и зачем».
- CPP → in-app flow: с iOS 18 custom product page может открыть соответствующий флоу; для Meta аналог — угол креатива через ad name (af_ad в PostHog доходит до ~10% юзеров, в 1.0.9 добавлен).

**Что работает**

- Непрерывность результата, а не механизма (Vahe, «Trojan horse»): реклама обещает «почти стоун», онбординг конвертирует это в привычку (логинг за 10 секунд), пейвол отвечает «это работает» (отзывы, дата цели), а не повторяет рекламу.
- Один заголовок → один CTA → та же цифра на кнопке и на Apple-листе (Gina Gotthilf: каждая кнопка это шаг воронки; Jeff/Jake: локализация «реально меняет конверсию»).
- Пейвол по источнику: organic/App Store → soft (чтобы не ловить злые отзывы), Meta → hard (анекдот AppStack/Superwall, без цифр). У нас Meta уже hard; для ASA/organic можно тестировать soft.

**Что берём себе**

- Welcome в двух вариантах под два рабочих угла: P1 result story («Lost nearly a stone without giving up Costa» + UK-лицо) и «logged in 10 seconds» демо; раздавать по af_ad или по ответу «откуда узнали».
- «3 days free» из рекламы повторить на welcome (лавр «3 days free, cancel anytime») и держать одну и ту же сумму на карточке, кнопке и Apple-листе в £.
- Hero пейвола из квиза: цель + дата + имя; для «just track» и maintain свой заголовок (сейчас maintain получает «Your zone: N kcal», just_track ничего).
- Source question вторым вопросом с рандомизированным порядком опций; ответ в PostHog как резервная атрибуция и ключ для веток.

## Best practices из YouTube (55 видео)


**Онбординг**

- Длина не рычаг: Mobbin среднее 25 экранов, Duolingo 60 до sign-up; Hannah видела победу короткого флоу по install→paid, Sociaal — длинного «happy friction». Общее у всех: ритм «спроси → верни ценность», каждые 2–4 вопроса что-то возвращать (даже захардкоженный интерстишл работает, Natalia/Adapty).
- Персонализация недоиспользована: 23% апов (AI-апы 7%) по Mobbin. Имя +133% активации (Hannah, один кейс), multi-select целей +10% триалов (Headspace), планы под ответы +20% апгрейдов (Grammarly), разговорный тон +5% (Dollar Shave Club).
- Порядок вопросов: лёгкие закрытые сначала, болевой позже, когда вложена минута (Vahe); болевой вопрос это прайминг, а не сбор данных. Отражать ответы с данными и поддержкой, не допрашивать; закрывающий summary «вас услышали» (Sociaal).
- Текст: каждый live-разбор начинается с «слишком много текста». Один визуал us-vs-them вместо абзаца; стримить текст чат-стилем; loss-framing «что будет, если продолжать угадывать» перед «и это легко» (GLP-1 кейс).
- Welltory: 60%+ конверсий приходят через месяцы после первого дня; первый экран — смелое частичное обещание, не повтор проблемы; «что ты теряешь, не начав сегодня» — шаг, который у них «не получался».
- Permissions: ATT первым (Hannah: «удваивает opt-in»), остальные с warm-up; rating prompt и «откуда узнали» после ценности (панель Adapty), но для UA-данных можно и раньше.
- Sign-in до ценности убивает конверсию (kb2Mco6Pcwk; Duolingo try-first +10% на Android). Коммитмент press-and-hold «повышает ARPU» (Vahe, без цифр).

**Пейвол**

- Дизайн-тесты > персонализация > упаковка цен > сама цена (Parra, 4,700 пейволов). Базовая простая версия: outcome-заголовок, 3–4 буллета, рейтинг, большая CTA с шевроном; простой пейвол бил таблицу на 111%, чистка названий планов +10%.
- Trial anxiety: «free» много раз, скрыть «3-day» на карточке, таймлайн + напоминание (лучше выбираемое: за 1/2/3 дня), «No payment due now» только на экране с ценой. Multi-step 20–40% аплифт (Vahe); «Subscribe» → «Start your 7-day free trial» 3% → 27% (Hannah).
- Противоречия, которые надо тестировать, а не выбирать: таймлайн vs отзывы на iOS (Parra vs Vahe); 2 плана (Parra, Patrick, Jake) vs «несколько цен всегда побеждают» (Hannah) vs annual+weekly без monthly (Max); триал на yearly (Hannah, Jake, Prehab +75% триалов) vs на monthly/weekly (Max); задержанный X +5–10% (Max) vs «трюки растят отмены» (Hannah).
- Transaction-abandonment paywall после отмены Apple-листа: только годовой со скидкой, недисконтированный меньший план как якорь (Vahe). Глубина скидки спорна: 80–90% (Vahe) vs 25–33% (Parra, «удешевляет продукт»).
- Цена: копировать рынок и начинать на 20% ниже (Cal AI), .99 работает немного, yearly ≈ 10× monthly, $29.99–40/год норма для AI-врапперов; weekly для nutrition «exploitative» и живёт месяц (Patrick), но A/B по триалам покажет его победителем — мерить 30–60-дневную выручку на установку.
- Видео продукта на пейволе: +80% конверсии в одном кейсе (Jake Moore), «video > timeline > bullets». Hard paywall: «вероятно приносит больше» (Vahe), Cal AI «единственное исключение» среди крупных; soft нужен, если есть привычка в первые дни.
- Cal AI: ~300 тестов пейвола за 18 месяцев (4 в неделю, 1–2 всегда live, 20–30 минут на запуск), один выигрыш $10–50K/мес; тестировать с ~100 юзеров в день.

**Alignment**

- Непрерывность outcome, не механизма: реклама останавливает скролл результатом, онбординг превращает его в привычку (Vahe «Trojan horse»); пейвол должен отвечать «это работает», а не повторять рекламу (Jake, Roast Ep3).
- «Люди ставят приложение, если есть проблема; стартуют триал, если верят, что решение работает» — proof на пейволе про результат, не про фичи.
- Один заголовок → одна CTA, value prop выше сгиба, каждая кнопка это шаг воронки (Gina Gotthilf, Duolingo: +10% от переписанного лендинга). Локализация под рынок «реально меняет конверсию» (Citizen, Mojo).
- Пейвол по источнику/точке входа: Citizen переставляет карусель по entry point; organic → soft, Meta → hard (анекдот); intent из ASA-группы/CPP выбирает вариант (Andy Carvell). С iOS 18 CPP открывает нужный флоу.
- Длина онбординга по awareness: unaware-аудитории нужна «лекция», solution-aware хотят меньше экранов; Vahe честно: «mixed results, depends on the market and the marketing». Повод варьировать онбординг по углу рекламы.
- Ожидания: разрыв между тем, что показала реклама, и тем, что получает юзер — главная причина отмен триала и рефандов в AI-апах (Natalia, Adapty).

**Где эксперты спорят**

- Таймлайн vs отзывы на iOS: Parra «таймлайн всё ещё очень сильный» / Vahe «данные: отзывы бьют таймлайн». Решение Vahe: таймлайн на отдельном reminder-экране, отзывы на экране с ценой.
- Число планов: 1 annual (Jake Moore) / 2 (Parra, Patrick) / annual+weekly (Max) / «несколько цен всегда побеждают» (Hannah).
- Где триал: только на annual (Hannah, Jake, Prehab) vs на monthly/weekly ради LTV 3–6 мес (Max).
- Жёсткость выхода: задержанный X +5–10% (Max), «not now» и no-exit как baseline (Jake) vs «трюки раздувают триалы и отмены, судить по revenue per install» (Hannah).
- Длина онбординга: короткий бил длинный по install→paid (Hannah) vs длинный «happy friction» (Sociaal) vs 80% completion на 20–30 шагах (Fastic, Andy Carvell).
- Пейвол сразу после онбординга (78% iOS-апов, Mobbin) vs «убрали пейвол, выручка выросла» (Pablo) vs «пейвол до aha, потому что 50% теряем до него» (Jake).

**Цифры спикеров (заявления)**

| Метрика | Значение | Кто |
|---|---|---|
| install → paywall | 80%+ хорошо, 90% отлично; 20–30% типично для $0.3–3M/мес | Parra (Mobbin), Jake Moore (Superwall) |
| install → trial | 3–7% рынок, 10–15% цель; 3–5% типично, 6.5–12% хорошо, ~20% потолок; 8.4% Deep Dive, 13% Prehab | Patrick Fon, Jake Moore |
| trial → paid | 25–30% рынок, 40–60% цель, «>30% хорошо» | Patrick Fon, Vahe |
| install → paid | 2–4% рынок, 6–10% цель; <6% верхний квартиль, 17% топ-5% (RevenueCat 2024) | Patrick Fon, Phil Carter |
| Multi-step trial paywall vs single | +20–40% | Vahe Bagdasaryan |
| Blinkist-style таймлайн | +21% trial start, +15% paid (MealTime) | RevenueCat Roast Ep1 |
| Outcome-экран перед пейволом | 7% → 17% trial sign-ups (Opal) | Mobbin |
| CTA «Subscribe» → «Start your 7-day free trial» | 3% → 27% | Hannah Parvaz |
| Триал только на annual | +75% триалов (Prehab) | RevenueCat Roast Ep3 |
| 7-дневный vs 3/14-дневный триал | ~10% лучше trial→paid у части апов | Max (Adapty) |
| Задержанный X (5–10 s) | +5–10% конверсии | Max (Adapty) |
| Тумблер триала | 5–10% покупают без триала при тех же триалах | Max (Adapty) |
| Ограниченная скидка 40% на 3-й день | 3× конверсий (медитация) | Nathan Hudson |
| Имя в онбординге (даже неиспользуемое) | +133% активации | Hannah Parvaz |
| Multi-select целей | +10% триалов (Headspace) | Mobbin |
| Планы под ответы квиза | +20% апгрейдов (Grammarly) | Mobbin |
| Тесты пейвола в год | ~133 в среднем; 10+ в год ≈ 2× рост | Adapty data via Patrick Fon |
| Cal AI тесты | ~300 за 18 мес, выигрыш $10–50K/мес каждый | Jake Castillo |

## Гипотезы

| ID | Волна | Блок | Что меняем | Метрика | Доказательства | Усилие | Уверенность |
|---|---|---|---|---|---|---|---|
| H1 | 1 | Paywall | **Цена на экране до Apple-листа.** В hero-пейвол вернуть карточку плана с крупной ценой в £ («£9.99/мес» или «£2.49/мес · billed £29.99/yr»), строку «3 дня бесплатно, затем £X», CTA с той же суммой. Terms-строка остаётся. | tap → purchase (12% → 30%+), install → trial | наши данные (цена только в 12 px, 84% отмен); все 11 конкурентов показывают цену до листа; Superwall «CTA показывает billed price»; Citizen/Mojo локализация | низкое (Adapty builder) | высокая |
| H2 | 1 | Paywall | **3-шаговая trial-подводка (Cal AI / Welmi / Lose It).** Экран 1: «We want you to try YumYummy for free» + таймлайн с точной датой списания и «No payment due now»; экран 2: колокольчик «We'll remind you a day before» (default-on, выбор дня); экран 3: пикер с 2 планами и отзывами. Payment-слова только с экрана 1 пейвола, не в квизе. | paywall → trial (3.8% → 10%+) | Cal AI, Welmi, Lose It (один шаблон); Vahe +20–40% multi-step; MealTime +21% на таймлайне; Blinkist exit-survey «не знал, когда спишут» | среднее (3 экрана в builder) | высокая |
| H3 | 1 | Paywall | **Второй шанс после отмены Apple-листа.** Включить pw_after_cancel, но переделать: не weekly £2.99, а год со скидкой 25–33% от $49.99-плана (отдельный продукт или промо-оффер в App Store Connect) + недисконтированный monthly как якорь; одна кнопка «Not now». Позже тот же экран на X soft-варианта. | recovered trials из 84% отмен; revenue per install | MyNetDiary (7-day trial modal после отмены листа), Vahe transaction-abandonment, Nathan 3× на лимитированной скидке; Parra против скидок >33% | низкое (переключатель + правка флоу) | высокая |
| H4 | 1 | Paywall | **2 плана: yearly $49.99 по умолчанию + monthly, без weekly.** Новый yearly $49.99 (одобрен Apple; UK-цену и intro offer проверить в ASC) по умолчанию в формате «≈£3.50/мес · billed yearly · Save 65%», monthly £9.99 второй. Weekly только как отдельный арм. Старый yearly $89.99 не использовать. | revenue per install за 30/60 дней, yearly share, tap → purchase | 10 из 11 конкурентов yearly default; Cal AI $29.99 (правило −20% от рынка); Patrick «третий план не берут», weekly для nutrition exploitative; Parra 2 плана «dramatic increase»; RevenueCat 2026: в H&F 68% подписок и 59% выручки на annual | низкое (Adapty builder; продукт уже есть) | средняя (контр-риск: weekly тянет кэш вперёд) |
| H5 | 1 | Paywall | **Outcome-заголовок и proof из квиза.** «We'll help you lose 6 kg by 12 December» (lose/gain), «Keep 2,100 kcal a day without the homework» (maintain/just track) + 2 реальных UK-отзыва со «stone» под заголовком; рейтинг App Store. Таймлайн остаётся на reminder-экране H2. | paywall → tap (32% → 40%+) | Yazio (reveal → заголовок дословно), Noom; Grammarly +20%; 4 агентства (Andy, Hannah, Nathan, Jake) против «Premium»-заголовков; Vahe: отзывы > таймлайн на iOS | низкое (custom tags уже есть) | средняя |
| H6 | 1 | Paywall | **Цена yearly: $49.99 против арма £29.99.** После H1–H4: арм yearly £29.99 (правило Cal AI «на 20% ниже рынка») против базового $49.99-плана при одинаковом monthly £9.99; .99-окончания; «Save X%» с честной арифметикой. Мерить revenue per install, не триалы. | revenue per paywall view, trial → paid | Jake Castillo: старт на 20% ниже рынка, итерировать; Phil Carter 5–15% от оптимизации цены; AllTrails $29.99 → $35.99 | низкое после H4 | средняя |
| H7 | 2 | Onboarding | **Welcome повторяет выигравшую рекламу.** Вариант A: result story («Nearly a stone lighter without giving up Costa», UK-лицо, «3 days free») + демо; вариант B: текущий «logged in ~10 seconds». Раздача по af_ad (P1 → A, P2 → B), где атрибуции нет — 50/50. | S1 → S2 (87% → 93%+), install → trial по углу | наш S1→S2 это главный drop до пейвола; Welltory «смелое частичное обещание»; Hannah «20% не помнят, зачем ставили»; никто из 12 не повторяет рекламу (свободное поле) | низкое | средняя |
| H8 | 2 | Onboarding | **Reflect-back и имя.** Вопрос «What should we call you?» после цели; интерстишл после S2 («Most people here want to lose 5–10 kg. You've got this, Nikita») и после S8 («Logging took too long for 61% of people who switched to us») с реальными цифрами; имя в plan reveal и заголовке пейвола. | S2 → S10 completion, paywall → tap | Yazio, MyNetDiary, Noom, MFP; Hannah +133% (имя), Sociaal «feel listened to»; Mobbin: персонализация у 23% | низкое | средняя |
| H9 | 2 | Onboarding | **Лекции S9/S10 → один визуал + loss-framing.** S9: одна картинка us-vs-them («people who track vs people who guess», 2× результат) без абзацев; S10: proof-карточка остаётся, текст в 2 строки; тест арма без S9 вообще для Meta-трафика. | S8 → paywall, время до пейвола, install → trial | все live-разборы Superwall «слишком много текста»; HPQkBqDHAQU loss-framing; Vahe: solution-aware не нужна лекция | низкое | средняя |
| H10 | 2 | Onboarding | **Plan reveal как награда: лоадер с отзывами → график с датой → «Commit».** N2 лоадер с 3–4 ротирующимися UK-отзывами (BitePal), N3 с графиком веса и датой для всех целей (для maintain «ваша зона»), кнопка «Commit to my goal» press-and-hold (Yazio/BitePal), затем «You've done the hard part» без слов про оплату. | paywall → tap | BitePal, Lose It, MyNetDiary, Yazio; Opal 7% → 17% от outcome-экрана; Vahe: press-and-hold растит ARPU; 3iW2 payment-слова до пейвола вредят | среднее (график в builder) | средняя |
| H11 | 2 | Onboarding | **Source question + «пробовали другие трекеры».** Q2 «Where did you hear about us?» (Instagram/Facebook, TikTok, App Store search, friend, other; порядок рандомный), Q3 «Tried other calorie trackers?» → ветка: бывшим MFP/Cal AI показывать «we checked 1,200 UK brands» proof, новичкам «10 seconds a meal». | атрибуция (self-reported vs af_*), completion | Cal AI Q3/Q4, BitePal Q1, Yazio Q2, Foodvisor Q3; Lose It ветвит аргумент по ответу; у нас af_* доходит до 10% | низкое | высокая (ценность данных), эффект на конверсию неизвестен |
| H12 | 2 | Onboarding | **UK-единицы и safety-флаг.** Stones/lb как первый вариант для GB, один тап «safe target −10%»; короткий флаг (беременность/РПП) с мягким выходом. | S6 → S7 (94% → 98%), trust | Nutracheck (UK-лидер по рейтингам), наш −6% на S6 | низкое | низкая по эффекту |
| H13 | 3 | Alignment | **Welcome и hero пейвола по углу рекламы.** af_ad/ad name → вариант welcome (H7) и заголовок пейвола: result-угол → «Nearly a stone by <date>», effortless-угол → демо-видео 5–8 s на пейволе; organic/ASA → soft-вариант с X. | install → trial по углу, revenue per install | Citizen entry-point карусель, Andy Carvell intent → вариант, Jake «тестируй месседж лучших ads», Vahe source → soft/hard (анекдот); Jake Moore видео на пейволе +80% | среднее (нужна доставка af_ad в Adapty custom attrs) | средняя |
| H14 | 3 | Paywall | **Soft-арм: X → ограниченный free → пейвол после первого лога.** 20% трафика: крестик на пейволе, 3 бесплатных лога, пейвол при 4-м и на day 2 push; сравнить install → trial за 7 дней и выручку. | trial за 7 дней, revenue per install, отзывы | Welltory 60% конверсий после дня 1; Pablo «убрали пейвол, выручка выросла»; Lifesum/Cronometer; риск: Vahe «hard приносит больше», Lose It рейтинг | среднее | низкая |
| H15 | 3 | Paywall | **7-дневный триал на yearly.** Арм yearly с 7-дневным триалом против 3-дневного; триал только на yearly, monthly без триала. | trial → paid, refunds, install → paid | RevenueCat 2026: trial→paid 25.5% при ≤4 днях vs 37.4% при 5–9; annual + ≤4 дня 24% vs 44.6% при длинных; 55% отмен 3-дневных в день 0; 54% H&F-апов на 5–9 днях. Max (Adapty) ~10% лучше у 7 дней; Prehab +75% триалов при триале только на annual. Против: 3 дня «safest» для AI-cost (SubHub). | низкое (intro offer в ASC) | средняя (корреляционные данные, нет чистого H&F-эксперимента) |

## План тестов

- **Волна 1 — пейвол (октябрь, первые 2–3 недели после аппрува build 61).** Цель: tap → purchase с 12% к 30%+, install → trial с 2.7% к 6%+. Гипотезы: H1, H2, H3, H4, H5. Один новый флоу pw_main_v2 в Adapty (3 экрана: free-подводка, reminder, пикер 2 планов yearly $49.99 + monthly, отзывы) против текущего S_hero; pw_after_cancel включить обоим армам сразу (не тест, а фикс). После победителя: H6 (арм £29.99).
- **Волна 2 — онбординг (ноябрь).** Цель: paywall → tap к 40%, S1 → S2 к 93%. Гипотезы: H7, H8, H9, H10, H11, H12. onb_main_v2 в Adapty: welcome A/B (H7), имя + 2 reflect-экрана (H8), S9 визуал (H9), лоадер с отзывами + график + commit (H10), source question (H11). Тестировать парой флоу, не по экрану: трафика ~80 пейволов в неделю.
- **Волна 3 — alignment (декабрь).** Цель: install → trial по углу рекламы, revenue per install по источнику. Гипотезы: H13, H14, H15. Нужна доставка af_ad / acquisition_source в Adapty custom attributes (код, не builder) и ASA/organic сегмент.

**Правила**

- Главная метрика любого теста пейвола: trial starts И 30-дневная выручка на установку (weekly выиграет по триалам и проиграет по деньгам).
- Триал-структуру судить по LTV: Adapty сообщает, что тесты структуры триала выигрывают по LTV в 59.6% случаев и по сырой конверсии только в 39.9%.
- Объём: ~70–80 показов пейвола в неделю на текущем спенде. Один A/B на 2 арма даёт ~35/неделю на арм; чтобы увидеть 12% → 25% на tap → purchase нужно ~100 тапов на арм, то есть 3–4 недели. Поэтому большие шаги (новый флоу целиком), не косметика.
- Последовательно, не параллельно: один тест на placement; следующий после победителя. Cal AI делал 4 в неделю при 100+ юзерах в день, у нас пока 10–15.
- Инструментировать: paywall_shown с variation_name уже есть; добавить purchase_cancelled с вариантом и экраном (сейчас cancel без variant), event на after-cancel оффер, и screen-level события builder-флоу (adapty_flow_custom_action).
- Не копировать колесо, таймеры без скидки и тумблер триала без проверки App Review; «money back» и «pay now, decide later» на нативном пейволе практики называют нарушением гайдлайнов.

## Пробелы

- Nutracheck не записан ни в ScreensDesign, ни в Mobbin: онбординг восстановлен по двум туториалам и 5 скриншотам стора, пейвол и цены неизвестны. По решению Никиты (1 окт) пока не углубляем.
- Записи ScreensDesign — US-сторфронт; Cal AI запись апреля 2026, MFP мая 2025, BitePal августа 2025. Для текущих UK-цен нужен ручной прогон 2–3 лидеров (Cal AI, BitePal, Yazio) на UK-устройстве.
- Decline path у hard-пейволов (Cal AI, Welmi) не записан: что происходит после отмены Apple-листа, неизвестно.
- Нет скриншота живого S_hero_v1 в отчёте (в репо только спецификация и builder-реплика варианта A). Стоит снять с симулятора для сравнения бок о бок.
- В PostHog paywall_purchase_cancelled не несёт variant: по армам отмены видны только через product. Исправить в следующем билде.

## Видео-источники

| id | канал | группа | название |
|---|---|---|---|
| [l0vswWcGmMs](https://www.youtube.com/watch?v=l0vswWcGmMs) | Superwall | calai | Meet The Marketing Genius Behind Cal AI |
| [QZnbu1_Itek](https://www.youtube.com/watch?v=QZnbu1_Itek) | Superwall | calai | Cal AI's Founder Reveals Why Accuracy Was Never the Point |
| [OxE79rpGioI](https://www.youtube.com/watch?v=OxE79rpGioI) | SubHub | calai | Cal AI's $40M ARR | Jake Castillo on the Truth About Scaling Apps in 2026 |
| [lkwX_kc0NS8](https://www.youtube.com/watch?v=lkwX_kc0NS8) | Superwall | paywall | I made 4,000 app paywalls and learned this |
| [24QMRDXck70](https://www.youtube.com/watch?v=24QMRDXck70) | Superwall | paywall | Our No-Code Apps Made $50M Using THIS Paywall |
| [E7RzEZ8GlHE](https://www.youtube.com/watch?v=E7RzEZ8GlHE) | Mobbin | paywall | He Tested 4,700 Paywalls. These Won. |
| [9ypqs_2fAl8](https://www.youtube.com/watch?v=9ypqs_2fAl8) | Mobbin | paywall | We Studied 2,995 Paywalls. Here's What Actually Converts. |
| [Qsq-Sj_rojU](https://www.youtube.com/watch?v=Qsq-Sj_rojU) | Mobbin | onboarding | I Studied 1,460 Onboarding Flows. Here's What I Found. |
| [_otKRaM5DRI](https://www.youtube.com/watch?v=_otKRaM5DRI) | SubHub | onboarding | We Studied 18,000+ Apps and Turned Their Onboardings Into Templates |
| [kYFmKH30YE8](https://www.youtube.com/watch?v=kYFmKH30YE8) | SubHub | onboarding | Creating onboarding flows that convert - Hannah Parvaz |
| [E_Amf9go2sg](https://www.youtube.com/watch?v=E_Amf9go2sg) | SubHub | onboarding | Boost Your Onboarding & Paywalls |
| [Tid8-QMfpEE](https://www.youtube.com/watch?v=Tid8-QMfpEE) | SubHub | paywall | Why your paywall is failing (and how to fix it) | Andy Carvell, Phiture |
| [rCgID3laJYE](https://www.youtube.com/watch?v=rCgID3laJYE) | SubHub | paywall | Roast your paywall for more revenue - Nathan Hudson |
| [i-TNRxuVdMY](https://www.youtube.com/watch?v=i-TNRxuVdMY) | SubHub | paywall | Workshop: Boost my paywall (Hannah Parvaz, Aperture) |
| [DWUwTC_HuG8](https://www.youtube.com/watch?v=DWUwTC_HuG8) | SubHub | pricing | Pricing strategies for scaling subscription mobile apps |
| [qfFkUt3Q8hg](https://www.youtube.com/watch?v=qfFkUt3Q8hg) | SubHub | pricing | Why a 3-Day Trial is Ideal for AI Applications |
| [JQzO7-usGnY](https://www.youtube.com/watch?v=JQzO7-usGnY) | SubHub | pricing | Monetizing AI Apps: Hybrid Models, Paywall Strategy & Apple Compliance |
| [T-fYaabrsPc](https://www.youtube.com/watch?v=T-fYaabrsPc) | SubHub | benchmarks | State of mobile subscriptions 2024 - Vitaly Davydov |
| [2VcdlEUaSY8](https://www.youtube.com/watch?v=2VcdlEUaSY8) | Superwall | onboarding | Why Skipping the Onboarding Intro Got Welltory a 90% Sync Rate |
| [PAHGHXz1xD8](https://www.youtube.com/watch?v=PAHGHXz1xD8) | Superwall | onboarding | The 6-Part Onboarding Framework Welltory's CPO Uses to Convert Users |
| [trfUsck1XHU](https://www.youtube.com/watch?v=trfUsck1XHU) | Superwall | onboarding | Welltory's CPO: Why 60% of Conversions Happen Months After Onboarding |
| [ND3Rtp81ATI](https://www.youtube.com/watch?v=ND3Rtp81ATI) | Superwall | onboarding | Why Most App Onboarding Fails (It's Not the Design) |
| [wIRgvmPLpZg](https://www.youtube.com/watch?v=wIRgvmPLpZg) | Superwall | onboarding | Why Perfect Copy Won't Save Your Onboarding |
| [1xvtIvKuDlg](https://www.youtube.com/watch?v=1xvtIvKuDlg) | Superwall | onboarding | The Onboarding Question That Makes Users Feel Understood |
| [RumPMj05hSY](https://www.youtube.com/watch?v=RumPMj05hSY) | Superwall | onboarding | The "Happy Friction" Trick Behind Sociaal's High-Converting Onboarding |
| [uwlXznbEaCA](https://www.youtube.com/watch?v=uwlXznbEaCA) | Superwall | onboarding | Why Your Onboarding Questions Feel Boring (And How to Fix It) |
| [HVYlDtl88BE](https://www.youtube.com/watch?v=HVYlDtl88BE) | Superwall | onboarding | Why Text-Heavy Onboarding Kills Conversion (Live UX Teardown) |
| [_CCPwbwrVFY](https://www.youtube.com/watch?v=_CCPwbwrVFY) | Superwall | onboarding | Your Onboarding Feels Like a Survey - Here's How to Fix It |
| [kb2Mco6Pcwk](https://www.youtube.com/watch?v=kb2Mco6Pcwk) | Superwall | onboarding | Forcing Sign-In Too Early Is Killing Your App's Conversions |
| [_LVXTb8NAnQ](https://www.youtube.com/watch?v=_LVXTb8NAnQ) | Superwall | onboarding | The Onboarding Mistake Killing Your Signups (Don't Ask This Too Soon) |
| [oJW3NTu4a0A](https://www.youtube.com/watch?v=oJW3NTu4a0A) | Superwall | onboarding | Should Onboarding Have 6 Feature Screens? It Depends on User Intent |
| [EeiZeVFq80Q](https://www.youtube.com/watch?v=EeiZeVFq80Q) | Superwall | onboarding | Onboarding Advice: If Your App Isn't Clear, Copy What's Already Working |
| [qHOA3ZisJwo](https://www.youtube.com/watch?v=qHOA3ZisJwo) | Superwall | onboarding | Why Your App's First Question Is Costing You Users (Onboarding Psychology) |
| [hEdA8NuMQbU](https://www.youtube.com/watch?v=hEdA8NuMQbU) | Superwall | onboarding | Why Overloaded Onboarding Copy Kills UX (And the Simple Fix) |
| [HPQkBqDHAQU](https://www.youtube.com/watch?v=HPQkBqDHAQU) | Superwall | onboarding | Why GLP-1 App Onboarding Should Scare Users First (Tactical Breakdown) |
| [VYc7CIK4kzs](https://www.youtube.com/watch?v=VYc7CIK4kzs) | Superwall | alignment | Why Your Paywall Should Change Based on Where Users Come From |
| [KhskHhccX1g](https://www.youtube.com/watch?v=KhskHhccX1g) | Superwall | paywall | This One Paywall Tweak Boosts Trial Conversions (Duolingo & Opal Use It) |
| [3iW2TuhcWLc](https://www.youtube.com/watch?v=3iW2TuhcWLc) | Superwall | paywall | Why Mentioning "Payment" Too Early Kills Your Paywall Conversions |
| [N2Vic7bfsTw](https://www.youtube.com/watch?v=N2Vic7bfsTw) | Superwall | paywall | Why User Reviews Beat Trial Timelines on iOS Paywalls - Vahe Bagdasaryan |
| [K_RCj8rQvuc](https://www.youtube.com/watch?v=K_RCj8rQvuc) | Superwall | paywall | Hard Paywall vs Soft Paywall: How to Actually Choose |
| [-fEz7m3N3cA](https://www.youtube.com/watch?v=-fEz7m3N3cA) | Superwall | paywall | They Removed the Paywall (Against Every Industry Rule) and Revenue Went Up |
| [zG-sGh-5Emg](https://www.youtube.com/watch?v=zG-sGh-5Emg) | Superwall | teardown | Live Coaching: Fixing App Paywalls & Growth in Real Time w/ Vahe Bagdasaryan |
| [sYosUxgngEE](https://www.youtube.com/watch?v=sYosUxgngEE) | Superwall | teardown | Growing $1,000,000/year Apps in 60 Mins - LIVE Coaching |
| [wHmJYasgEMY](https://www.youtube.com/watch?v=wHmJYasgEMY) | Superwall | pricing | Why $17.99 Beats $18: The Pricing Psychology Trick |
| [R2WUDlhlPrk](https://www.youtube.com/watch?v=R2WUDlhlPrk) | Superwall | pricing | Weekly Pricing Is a Trap: Why It Kills Your App's Exit Value |
| [n6f0UVbATng](https://www.youtube.com/watch?v=n6f0UVbATng) | RevenueCat | paywall | The risks and rewards of paywalling a free feature - lessons from Lose It! |
| [S7hXjUmNKuw](https://www.youtube.com/watch?v=S7hXjUmNKuw) | RevenueCat | alignment | They clicked on my ad, now what? How to optimize landing pages and onboarding - Gina Gotthilf |
| [lGqaDZJ4bFI](https://www.youtube.com/watch?v=lGqaDZJ4bFI) | RevenueCat | paywall | How to build great paywalls |
| [OLxuOVx41so](https://www.youtube.com/watch?v=OLxuOVx41so) | RevenueCat | paywall | How to Optimize Your App's Paywall |
| [4Mt7IboooGk](https://www.youtube.com/watch?v=4Mt7IboooGk) | RevenueCat | teardown | Roast My Paywall: Live! Episode 3 |
| [nCvsQc-VrTM](https://www.youtube.com/watch?v=nCvsQc-VrTM) | RevenueCat | teardown | Roast My Paywall: Live! Episode 1 |
| [eCTD91y89AM](https://www.youtube.com/watch?v=eCTD91y89AM) | RevenueCat | benchmarks | The Subscription Value Loop - Phil Carter |
| [roRqz7X-xqc](https://www.youtube.com/watch?v=roRqz7X-xqc) | YouTube | nutracheck | How To Use Nutra Check PART 1 | Beginners Guide (Evolve With Kat) |
| [WHRQWLSrfyY](https://www.youtube.com/watch?v=WHRQWLSrfyY) | YouTube | nutracheck | Nutracheck Tutorial (William Carlisle) |
| [QmD_QZvRi3A](https://www.youtube.com/watch?v=QmD_QZvRi3A) | YouTube | nutracheck | 4 Reasons why I use Nutracheck over Myfitnesspal (Lewis Neill) |