/**
 * TypeScript mirrors of the Phase 1 backend schemas
 * (`app/schemas/app_api.py`, `app/schemas/auth.py`, `app/schemas/meal.py`,
 * `app/schemas/saved_meal.py`, `app/schemas/ai.py`).
 */

export type AccessStatus =
  | 'new'
  | 'trial'
  | 'active'
  | 'trial_expired'
  | 'expired';

export type AccuracyLevel = 'EXACT' | 'ESTIMATE' | 'APPROX';

export interface BillingSnapshot {
  access_status: string;
  trial_started_at?: string | null;
  trial_ends_at?: string | null;
  trial_days_remaining?: number | null;
  subscription_plan_id?: string | null;
  subscription_ends_at?: string | null;
  subscription_auto_renew?: boolean | null;
  subscription_provider?: string | null;
  usage_cost_current_period: number;
  usage_cap_usd?: number | null;
  usage_exceeded: boolean;
}

export interface AccountProfile {
  account_id: number;
  user_id: number;
  telegram_id?: string | null;
  linked_providers: string[];
  goal_type?: string | null;
  gender?: string | null;
  age?: number | null;
  height_cm?: number | null;
  weight_kg?: number | null;
  activity_level?: string | null;
  target_calories?: number | null;
  target_protein_g?: number | null;
  target_fat_g?: number | null;
  target_carbs_g?: number | null;
  onboarding_completed: boolean;
  timezone?: string | null;
  billing: BillingSnapshot;
}

export interface AccountProfileUpdate {
  goal_type?: string | null;
  gender?: string | null;
  age?: number | null;
  height_cm?: number | null;
  weight_kg?: number | null;
  activity_level?: string | null;
  target_calories?: number | null;
  target_protein_g?: number | null;
  target_fat_g?: number | null;
  target_carbs_g?: number | null;
  onboarding_completed?: boolean | null;
  timezone?: string | null;
}

export interface MealItem {
  name: string;
  grams?: number | null;
  calories_kcal?: number | null;
  protein_g?: number | null;
  fat_g?: number | null;
  carbs_g?: number | null;
  source_url?: string | null;
}

/** HOW the agent obtained the numbers (additive, 25(1)+). */
export type AssessmentMethod =
  | 'label'
  | 'off'
  | 'official'
  | 'web'
  | 'usda'
  | 'usda_components'
  | 'photo'
  | 'estimate';

export interface MealAssessment {
  method: AssessmentMethod | string;
  domain?: string | null;
  portion_estimated?: boolean;
  verified_items?: number;
  total_items?: number;
}

export interface MealRead {
  id: number;
  eaten_at: string;
  description_user: string;
  calories: number;
  protein_g: number;
  fat_g: number;
  carbs_g: number;
  accuracy_level?: AccuracyLevel | null;
  /** Primary source the macros were checked against (real meals). */
  source_url?: string | null;
  /** Per-ingredient breakdown for AI-logged meals. */
  items?: MealItem[];
  /** HOW the numbers were obtained (25(1)+ AI-logged meals). */
  assessment?: MealAssessment | null;
  /** Display-only source label (mocks); real entries use source_url. */
  source?: string;
}

export interface DaySummary {
  user_id: number;
  date: string;
  total_calories: number;
  total_protein_g: number;
  total_fat_g: number;
  total_carbs_g: number;
  meals: MealRead[];
}

/** Lightweight per-day aggregate for the Week tab's history/streak (25(1)+).
 *  `GET /app/history` returns these WITHOUT the meal breakdown. */
export interface DayTotals {
  date: string;
  total_calories: number;
  total_protein_g: number;
  total_fat_g: number;
  total_carbs_g: number;
  meal_count: number;
}

export interface AppMealCreate {
  date: string; // YYYY-MM-DD
  description_user: string;
  calories: number;
  protein_g?: number;
  fat_g?: number;
  carbs_g?: number;
  accuracy_level?: AccuracyLevel;
  /** Optional component breakdown (25(1)+), preserved for later editing. */
  items?: MealItem[];
  source_url?: string | null;
}

/** PATCH /app/meals/{id} (25(1)+). `items` replaces the breakdown and drives
 *  the totals; explicit total fields override the recomputed values. */
export interface MealUpdateInput {
  description_user?: string;
  calories?: number;
  protein_g?: number;
  fat_g?: number;
  carbs_g?: number;
  items?: MealItem[];
}

/** PATCH /app/saved-meals/{id} (25(1)+). Same semantics as MealUpdateInput. */
export interface SavedMealUpdateInput {
  name?: string;
  total_calories?: number;
  total_protein_g?: number;
  total_fat_g?: number;
  total_carbs_g?: number;
  items?: MealItem[];
}

export interface SavedMealListItem {
  id: number;
  name: string;
  total_calories: number;
  total_protein_g: number;
  total_fat_g: number;
  total_carbs_g: number;
  use_count: number;
  /** Component breakdown (25(1)+); empty for older saves. */
  items?: MealItem[];
}

export interface SavedMealsListResponse {
  items: SavedMealListItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface WorkflowTotals {
  calories_kcal: number;
  protein_g: number;
  fat_g: number;
  carbs_g: number;
}

export interface WorkflowItem {
  name: string;
  grams?: number | null;
  calories_kcal: number;
  protein_g: number;
  fat_g: number;
  carbs_g: number;
  source_url?: string | null;
}

export interface WorkflowRunResponse {
  intent: string;
  message_text: string;
  confidence?: string | null;
  totals: WorkflowTotals;
  items: WorkflowItem[];
  source_url?: string | null;
  /** HOW the numbers were obtained (25(1)+ servers; null from older ones). */
  assessment?: MealAssessment | null;
}

export interface AppAgentRunRequest {
  text: string;
  image_url?: string | null;
  /** Multi-photo meals (25(1)+). `image_url` stays set to the first photo so
   *  the request also works against an older server. */
  image_urls?: string[] | null;
  force_intent?: string | null;
  nutrition_context?: string | null;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  account_id: number;
  created: boolean;
}

export interface EmailCodeRequestResponse {
  sent: boolean;
  debug_code?: string | null;
}

export interface TelegramLinkRedeemResponse {
  status: string; // 'linked' | 'already_linked'
  account_id: number;
}

/** Reverse linking: the signed-in app mints a code + a t.me deep link the user
 *  opens to connect their Telegram bot. */
export interface AppLinkIssueResponse {
  code: string;
  expires_in_seconds: number;
  bot_username: string;
  deep_link: string;
}

export interface PresignResponse {
  key: string;
  upload_url: string;
  public_url?: string | null;
  expires_in_seconds: number;
}

export interface TrialStartResponse {
  access_status: string;
  trial_started_at?: string | null;
  trial_ends_at?: string | null;
  trial_days: number;
  already_started: boolean;
}
