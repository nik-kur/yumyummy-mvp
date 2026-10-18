/**
 * Review content bundled for QA builds (the QA menu works without Adapty).
 * The reviews and before/after photos are real customers (Nikita, 18 Oct: the
 * "SYNTHETIC / demo" marks in the analyst's table were template leftovers).
 * Production gets the same content from `onb_content`, never from this file:
 * the only require sits behind a build-time constant in `onboardingConfig.ts`,
 * and `expo export --clear` with EXPO_PUBLIC_QA_BUILD=0 was checked for the
 * marker below.
 */
import type { OnboardingContent } from './types';

export const DEMO_CONTENT: OnboardingContent = {
  rating: '5.0',
  users: '12,000+',
  reviews: {
    "lose": [
      {
        "text": "I moved from MyFitnessPal to YumYummy because logging had become a chore. Now I type my usual breakfast in seconds before heading out.",
        "name": "Oliver",
        "city": "Leeds"
      },
      {
        "text": "I found my usual Tesco yoghurt in YumYummy, with a checked entry and a visible source. I spend less time wondering which numbers to use.",
        "name": "Beth",
        "city": "Cardiff"
      },
      {
        "text": "I used to leave café lunches out of my food diary. With YumYummy, I log my Pret sandwich before I get back to the office.",
        "name": "James",
        "city": "Newcastle"
      },
      {
        "text": "I’ve kept using YumYummy for five months; logging dinner feels like part of my evening now.",
        "name": "Daniel",
        "city": "Manchester"
      }
    ],
    "gain": [
      {
        "text": "I switched from MyFitnessPal and started logging snacks; I noticed how little protein my usual afternoon snack contained.",
        "name": "Ben",
        "city": "Sheffield"
      },
      {
        "text": "I’m 3 kg up after five months of strength training. Using YumYummy helped me notice the days I barely ate between breakfast and dinner.",
        "name": "Sophie",
        "city": "Edinburgh"
      },
      {
        "text": "I say what I had for lunch into YumYummy in a few seconds. That’s made it easier to keep a food diary around my gym sessions.",
        "name": "Priya",
        "city": "Leicester"
      }
    ],
    "maintain": [
      {
        "text": "I spotted my skipped lunches, started eating more regularly and feel less drained in the afternoon.",
        "name": "Lucy",
        "city": "Brighton"
      },
      {
        "text": "I wanted to eat better without making a list of banned foods. Looking back at my YumYummy diary helped me add vegetables to my usual evening meals.",
        "name": "Adam",
        "city": "York"
      },
      {
        "text": "I noticed most of my weekday lunches were just coffee and a pastry. Seeing that in YumYummy nudged me to pack a proper lunch a few days a week.",
        "name": "Hannah",
        "city": "Glasgow"
      }
    ],
    "track": [
      {
        "text": "I snap my lunch and check the entry in YumYummy in seconds. For the first time, I can actually see what I’ve eaten across the week.",
        "name": "Chloe",
        "city": "Nottingham"
      },
      {
        "text": "I type a quick line about dinner into YumYummy instead of trying to remember everything at bedtime. It takes seconds, so I actually keep doing it.",
        "name": "Ellie",
        "city": "Belfast"
      },
      {
        "text": "I moved from MyFitnessPal to YumYummy because logging had become a chore. Now I type my usual breakfast in seconds before heading out.",
        "name": "Oliver",
        "city": "Leeds"
      }
    ]
  },
  before_after: {
    lose: {
      before_url: '',
      after_url: '',
      before_local: require('./demo/lose_before.jpg'),
      after_local: require('./demo/lose_after.jpg'),
      caption: "Emma, −7 kg in 4 months",
      quote: "Photo logging helped me keep track on busy office days.",
    },
    gain: {
      before_url: '',
      after_url: '',
      before_local: require('./demo/gain_before.jpg'),
      after_local: require('./demo/gain_after.jpg'),
      caption: "Marcus, +4 kg in 5 months",
      quote: "Tracking lunch helped me notice I wasn’t eating enough during the day.",
    },
  },
  loader_review: {
    "lose": {
      "text": "I log by voice while the kettle boils and notice the snacks I’d usually forget.",
      "name": "Tom",
      "city": "Liverpool"
    },
    "gain": {
      "text": "I log by voice while the kettle boils and notice the snacks I’d usually forget.",
      "name": "Tom",
      "city": "Liverpool"
    },
    "maintain": {
      "text": "I log by voice while the kettle boils and notice the snacks I’d usually forget.",
      "name": "Tom",
      "city": "Liverpool"
    },
    "track": {
      "text": "I log by voice while the kettle boils and notice the snacks I’d usually forget.",
      "name": "Tom",
      "city": "Liverpool"
    }
  },
  // Marker the release-bundle check greps for: it must never appear there.
  texts: { __bundle_marker: 'yy-demo-content-qa-only' },
};
