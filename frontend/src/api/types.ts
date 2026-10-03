/** Types mirroring the backend OpenAPI contract (hand-written, kept small). */

export type Gender = 'f' | 'm' | 'x';
export type Language = 'de' | 'en';
export type PaymentMethod = 'on_site' | 'sepa_debit' | 'sumup';
export type PaymentStatus = 'pending' | 'paid' | 'cancelled';
export type RegistrationStatus = 'pending' | 'confirmed' | 'cancelled';
export type AgeClassScheme = 'five' | 'one' | 'none';
export type Role = 'admin' | 'race_office' | 'timing' | 'sponsor_management' | 'sepa' | 'viewer';
export const ALL_ROLES: Role[] = ['admin', 'race_office', 'timing', 'sponsor_management', 'sepa', 'viewer'];

// ---- public ----

export interface PublicCompetition {
  id: string;
  title_de: string;
  title_en: string;
  start_time: string | null;
  price_adult_cents: number;
  price_youth_cents: number | null;
  relay_scoring: boolean;
}

export interface PublicEvent {
  id: string;
  name: string;
  year: number;
  event_date: string | null;
  registration_deadline: string | null;
  registration_open: boolean;
  tshirt_options: string[];
  tshirt_included: boolean;
  youth_cutoff_date: string | null;
  photos_available: boolean;
  competitions: PublicCompetition[];
}

export interface SponsorDisplay {
  mode: 'rotation' | 'marquee' | string | null;
  marquee_seconds: number;
  tier_weights: string | null;
}

export interface PublicInfo {
  organization: { name: string; slug: string };
  logo_url: string | null;
  payment_methods: PaymentMethod[];
  heard_about_options: string[];
  sepa_creditor: { name: string; creditor_id: string };
  sponsor_display: SponsorDisplay;
  events: PublicEvent[];
}

export interface PublicSponsor {
  id?: string;
  tier: number;
  name: string | null;
  url: string | null;
  image_url: string;
}

export interface PaymentView {
  method: PaymentMethod | string;
  status: PaymentStatus | string;
  amount_cents: number;
  iban_masked?: string | null;
  account_holder?: string | null;
  mandate_reference?: string | null;
  provider_transaction_code?: string | null;
  paid_at?: string | null;
  sepa_exported_at?: string | null;
}

export interface RegistrationCreate {
  event_id: string;
  competition_id: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  gender: Gender;
  email: string;
  language: Language;
  team_name?: string | null;
  tshirt_size?: string | null;
  postal_code?: string | null;
  heard_about?: string | null;
  consent_data: boolean;
  consent_publish: boolean;
  payment_method: PaymentMethod;
  iban?: string | null;
  account_holder?: string | null;
}

export interface OfficeRegistrationCreate extends RegistrationCreate {
  status: 'pending' | 'confirmed';
}

export interface RegistrationCreated {
  registration_id: string;
  bib_number: number;
  manage_url: string;
  checkout_url?: string | null;
  payment: PaymentView;
}

export interface ManageView {
  registration_id: string;
  status: string;
  event_id: string;
  event_name: string;
  event_year: number;
  competition_id: string;
  competition_title: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  gender: string;
  email: string;
  language: string;
  team_name: string | null;
  tshirt_size: string | null;
  bib_number: number | null;
  finish_seconds: string | null;
  frozen: boolean;
  payment: PaymentView;
  checkout_url?: string | null;
  photo_url?: string | null;
  mandate_text?: string | null;
  tshirt_options: string[];
  competitions: PublicCompetition[];
}

export interface ManageUpdate {
  email?: string;
  competition_id?: string;
  team_name?: string;
  tshirt_size?: string;
}

export interface ResultRow {
  place: number | null;
  bib_number: number | null;
  name: string;
  team_name: string | null;
  age_class: string | null;
  place_age_class: number | null;
  place_gender: number | null;
  gender: string;
  time: string;
  finish_seconds: number | null;
  relay_place: number | null;
  relay_total: number | null;
  relay_time: string;
}

export interface PublicResults {
  events: Array<{ id: string; name: string; year: number }>;
  event: { id: string; name: string; year: number } | null;
  competitions: Array<{ competition: PublicCompetition; rows: ResultRow[] }>;
}

// ---- auth ----

export interface MeResponse {
  email: string;
  display_name: string;
  roles: string[];
  organization: { id: string; slug: string; name: string };
  is_platform_admin: boolean;
  csrf_token?: string | null;
}

export interface VersionInfo {
  backend: string | null;
  db_schema: string | null;
}

// ---- events ----

export interface CompetitionIn {
  title_de: string;
  title_en: string;
  start_time: string | null;
  price_adult_cents: number;
  price_youth_cents: number | null;
  age_class_scheme: AgeClassScheme;
  gender_scoring: boolean;
  relay_scoring: boolean;
  bib_range_start: number | null;
  bib_range_end: number | null;
  sort_order: number;
}

export interface CompetitionOut extends CompetitionIn {
  id: string;
  event_id: string;
}

export interface EventIn {
  name: string;
  year: number;
  event_date: string | null;
  registration_deadline: string | null;
  default_start_time: string | null;
  tshirt_options: string;
  tshirt_included: boolean;
  youth_cutoff_date: string | null;
  venue_postal_code: string | null;
  bib_start_number: number;
  certificate_offset_lines: number;
  photo_base_url: string | null;
  photo_hmac_seed?: string | null;
}

export interface EventUpdate extends Partial<EventIn> {
  clear_fields?: string[];
}

export interface EventOut extends Omit<EventIn, 'photo_hmac_seed'> {
  id: string;
  photo_seed_set: boolean;
  has_certificate_background: boolean;
  has_bib_background: boolean;
  registration_count: number;
  competitions: CompetitionOut[];
}

export interface EventTemplate {
  template_version?: number;
  name: string;
  tshirt_options: string;
  tshirt_included: boolean;
  venue_postal_code: string | null;
  bib_start_number: number;
  certificate_offset_lines: number;
  competitions: CompetitionIn[];
}

export interface EventImportBody extends EventIn {
  competitions: CompetitionIn[];
}

// ---- registrations (team) ----

export interface RegistrationListItem {
  id: string;
  bib_number: number | null;
  first_name: string;
  last_name: string;
  birth_date: string;
  gender: string;
  competition_id: string;
  competition_title: string;
  team_name: string | null;
  status: string;
  finish_seconds: string | null;
  payment_method: string | null;
  payment_status: string | null;
  amount_cents: number | null;
  email: string;
}

export interface RegistrationDetail extends RegistrationListItem {
  event_id: string;
  participant_id: string;
  language: string;
  tshirt_size: string | null;
  postal_code: string | null;
  heard_about: string | null;
  consent_data: boolean;
  consent_publish: boolean;
  relay_id: string | null;
  created_at: string;
  payment: PaymentView | null;
}

export interface PagedRegistrations {
  items: RegistrationListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface RegistrationAdminUpdate {
  status?: RegistrationStatus;
  bib_number?: number;
  competition_id?: string;
  first_name?: string;
  last_name?: string;
  birth_date?: string;
  gender?: Gender;
  email?: string;
  language?: Language;
  team_name?: string | null;
  tshirt_size?: string | null;
  postal_code?: string | null;
  heard_about?: string | null;
  consent_data?: boolean;
  consent_publish?: boolean;
  finish_seconds?: number | string | null;
  clear_finish?: boolean;
  payment_method?: PaymentMethod;
  payment_status?: PaymentStatus;
  amount_cents?: number;
  account_holder?: string | null;
  iban?: string | null;
}

// ---- timing ----

export interface TimingContext {
  organization: { name: string; slug: string };
  actor: string;
  device: boolean;
  offset_seconds: number;
  events: Array<{
    id: string;
    name: string;
    year: number;
    competitions: Array<{ id: string; title_de: string; start_time: string | null }>;
  }>;
}

export interface RecordIn {
  bib_number: number;
  absolute_time: string;
  dedup_key: string;
}

export interface RecordOut {
  id: string;
  event_id: string;
  bib_number: number;
  absolute_time: string;
  source_label: string | null;
  status: string;
  dedup_key: string;
  created_at: string;
}

export interface DeviceTokenOut {
  id: string;
  label: string;
  time_offset_seconds: number;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
}

export interface DeviceTokenIssued extends DeviceTokenOut {
  token: string;
  kiosk_url: string;
}

export interface ComputeResult {
  computed: number;
  without_start_time: number;
  relays_formed: number;
}

export interface PlausibilityResult {
  threshold_seconds: number;
  entries: Array<{ bib_number: number; spread_seconds: number; timestamps: string[] }>;
}

export interface InternalResultRow extends ResultRow {
  consent_publish: boolean;
  registration_id: string;
}

export interface InternalResults {
  event: { id: string; name: string; year: number };
  competitions: Array<{
    competition: { id: string; title_de: string; relay_scoring: boolean };
    rows: InternalResultRow[];
    unfinished: number;
    relays: Array<{
      relay_id: string;
      team_name: string;
      place: number | null;
      total_scored: number;
      complete: boolean;
      total_seconds: number | null;
    }>;
  }>;
}

// ---- results / certificates ----

export interface ResultsOverview {
  event: { id: string; name: string; year: number };
  competitions: Array<{
    competition: { id: string; title_de: string; age_class_scheme: AgeClassScheme; gender_scoring: boolean };
    finished: number;
    age_classes: Array<{ age_class: string; counts: Record<string, number>; total: number }>;
  }>;
}

// ---- sponsors ----

export interface SponsorOut {
  id: string;
  tier: number;
  name: string | null;
  url: string | null;
  image_url: string;
}

export interface DisplaySettings {
  sponsor_mode: string;
  sponsor_marquee_seconds: string | number;
  sponsor_bucket_url: string;
  sponsor_tier_weights: string;
  bucket_validation?: { normalized_url: string; found: Record<string, number> } | null;
}

// ---- stats ----

export interface StatsPerson {
  name: string;
  age: number;
  bib_number: number | null;
}
export interface StatsFast {
  name: string;
  time: string;
  bib_number: number | null;
}
export interface EventStats {
  event: { id: string; name: string; year: number; venue_postal_code: string | null };
  overview: {
    participants: number;
    finished: number;
    teams: number;
    relays: number;
    relays_complete: number;
    average_age: number | null;
    youngest: StatsPerson | null;
    oldest: StatsPerson | null;
  };
  competitions: Array<{
    competition: { id: string; title_de: string };
    total: number;
    finished: number;
    by_gender: Record<string, number>;
    youngest: StatsPerson | null;
    oldest: StatsPerson | null;
    fastest: StatsFast | null;
    fastest_female: StatsFast | null;
    fastest_male: StatsFast | null;
  }>;
  relays: Array<{
    competition: string;
    team_name: string;
    place: number | null;
    complete: boolean;
    time: string;
    members: number;
  }>;
  team_names: string[];
  travel: {
    available: boolean;
    counted: number;
    unknown: number;
    buckets: Record<string, number>;
    average_km: number | null;
    farthest_km: number | null;
    farthest_region: string | null;
    top_regions: Array<{ region: string; name: string; count: number }>;
  };
  regulars: { count: number; names: string[] };
  heard_about: Record<string, number>;
  tshirt_sizes: Record<string, number>;
}

// ---- sepa ----

export interface SepaSummary {
  open: { count: number; amount_cents: number };
  exported: { count: number; amount_cents: number };
  creditor_name: string;
  creditor_id: string;
}

// ---- settings ----

export type SettingsView = Record<string, string | boolean>;

export interface SettingsUpdate {
  values: Record<string, string>;
  confirm_live_mail?: boolean;
}

// ---- users ----

export interface UserOut {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  roles: string[];
}

// ---- platform ----

export interface PlatformMe {
  email: string;
  csrf_token?: string | null;
  acting_organization: { id: string; slug: string; name: string } | null;
}

export interface OrganizationOut {
  id: string;
  slug: string;
  name: string;
  status: 'active' | 'suspended' | string;
  contact_email: string | null;
  created_at: string;
  events: number;
  registrations: number;
  users: number;
  storage_bytes: number;
}

export interface PlatformOverview {
  organizations: number;
  events: number;
  registrations: number;
  storage_bytes: number;
  db_size_bytes: number;
}

export interface AuditEntry {
  id: string;
  admin: string | null;
  organization_id: string | null;
  action: string;
  method: string | null;
  path: string | null;
  detail: unknown;
  created_at: string;
}

export interface PlatformAdminOut {
  id: string;
  email: string;
  is_active: boolean;
  is_self: boolean;
}

export type PlatformSettings = Record<string, string | number | boolean | null>;
