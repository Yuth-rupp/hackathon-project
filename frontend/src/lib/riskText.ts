import type { RiskLevel } from "@/types";

export type RiskLang = "EN" | "KM";

export const RISK_FACTOR_KEYS = [
  "rainfall",
  "hydrology",
  "soil",
  "seasonal",
  "historical",
] as const;

export const LEVEL_COLORS: Record<RiskLevel, string> = {
  low: "#22c55e",
  moderate: "#f59e0b",
  high: "#f97316",
  very_high: "#ef4444",
};

export const FACTOR_COLORS: Record<string, string> = {
  rainfall: "#38bdf8",
  hydrology: "#06b6d4",
  soil: "#10b981",
  seasonal: "#a855f7",
  historical: "#f59e0b",
};

// ---------------------------------------------------------
// English
// ---------------------------------------------------------

const EN = {
  title: "AI Flood Hazard & Multi-Factor Risk Assessment",
  subtitle:
    "Flood risk, contributing factors and data quality for the five Tonle Sap provinces.",
  refresh: "Refresh",
  runAssessment: "Recalculate",
  running: "Calculating...",
  loading: "Loading risk assessments...",
  loadingSub: "Connecting to the backend API",
  errorTitle: "Unable to Load Risk Assessments",
  tryAgain: "Try Again",
  emptyTitle: "No Risk Assessments Available",
  emptyBody:
    "The backend did not return any assessments. Check the database and the /risk/assessments API.",
  staleNotice:
    "This assessment is {age} old. Press Recalculate to use the newest weather and river data.",

  levels: {
    low: "Low",
    moderate: "Moderate",
    high: "High",
    very_high: "Very High",
  } as Record<RiskLevel, string>,

  summary: {
    highest: "Highest Risk",
    average: "Basin Average Score",
    elevated: "Locations at High or Above",
    coverage: "Average Data Coverage",
    of: "of {n}",
  },

  scale: {
    title: "Risk Scale",
    low: "0 - 24",
    moderate: "25 - 49",
    high: "50 - 74",
    very_high: "75 - 100",
  },

  cards: { score: "Risk Score", driver: "Main driver", rank: "Rank" },

  map: { title: "Basin Risk Map", hint: "Select a pin to inspect" },

  compare: {
    title: "Province Comparison",
    hint: "Click a bar to select",
  },

  detail: {
    current: "Current Risk Assessment",
    overall: "Overall Risk Score",
    category: "{level} risk category",
    driver: "Primary Risk Driver",
    whyTitle: "Why this score",
    actionsTitle: "Recommended Actions",
    assessedAt: "Assessed",
    notAvailable: "Not available",
  },

  quality: {
    title: "Data Quality",
    coverage: "Data Coverage",
    coverageHelp:
      "Share of the model weight that had usable data. Missing factors are left out and the rest are re-weighted.",
    status: "Status",
    good: "Good",
    partial: "Partial",
    limited: "Limited",
    unknown: "Unknown",
    freshness: "Source freshness",
    weather: "Weather & soil",
    discharge: "River discharge",
    waterLevel: "Gauge water level",
    fresh: "Fresh",
    stale: "Stale",
    noData: "No data",
    ago: "{age} ago",
    excludedTitle: "Not used in this score",
    excludedBody:
      "{names} had no usable data, so the score is based on the remaining factors only.",
  },

  factors: {
    title: "Contributing Factors",
    scoreHint: "Factor score out of 100",
    weight: "Weight",
    score: "Score",
    contribution: "Contribution",
    share: "Share of total score",
    none: "No contributing factor data available",
    noneBody: "The API did not return factor information for this location.",
    names: {
      rainfall: "Rainfall",
      hydrology: "Hydrology",
      soil: "Soil moisture",
      seasonal: "Seasonal",
      historical: "Historical",
    } as Record<string, string>,
    help: {
      rainfall: "Rain accumulated over the last 3, 7 and 30 days.",
      hydrology: "River discharge and gauge level compared with alarm levels.",
      soil: "How saturated the soil already is.",
      seasonal: "Position in the Tonle Sap flood-pulse calendar.",
      historical: "How often this location has flooded in the past.",
    } as Record<string, string>,
    details: {
      rain_3d_mm: "3-day rain",
      rain_7d_mm: "7-day rain",
      rain_30d_mm: "30-day rain",
      discharge_m3s: "Discharge",
      water_level_m: "Water level",
      alarm_level_m: "Alarm level",
      soil_moisture_vol: "Soil moisture",
      day_of_year: "Day of year",
      source_value: "Flood frequency",
    } as Record<string, string>,
  },

  method: {
    title: "How the score is calculated",
    c1Tag: "Weighted score",
    c1Title: "0 - 100 risk score",
    c1Body:
      "Each factor is scored from 0 to 100, multiplied by its weight and added up. Missing factors are removed and the remaining weights are re-normalised.",
    c2Tag: "Inputs",
    c2Title: "Five risk factors",
    c2Body:
      "Rainfall (25%), hydrology (30%), soil moisture (15%), seasonal conditions (15%) and historical flood frequency (15%).",
    c3Tag: "Data quality",
    c3Title: "Coverage & freshness",
    c3Body:
      "Weather and river data older than 48 hours is treated as stale and excluded rather than guessed.",
    version: "Model Version",
    type: "Model Type",
    disclaimer:
      "This is a rule-based score, not a calibrated flood probability. Use it together with official warnings.",
  },

  actions: {
    low: [
      "Continue routine monitoring.",
      "Check the forecast again in the next update.",
    ],
    moderate: [
      "Monitor rainfall and river conditions regularly.",
      "Review local flood-response contacts.",
    ],
    high: [
      "Prepare flood-response resources.",
      "Alert vulnerable communities and floating villages.",
      "Check evacuation routes and shelters.",
    ],
    very_high: [
      "Prioritise emergency response.",
      "Assess evacuation needs now.",
      "Follow official NCDM warnings (hotline 1294).",
    ],
  } as Record<RiskLevel, string[]>,
};

export type RiskDictionary = typeof EN;

// ---------------------------------------------------------
// Khmer
// ---------------------------------------------------------

const KM: RiskDictionary = {
  title: "ការវាយតម្លៃហានិភ័យទឹកជំនន់ដោយ AI",
  subtitle:
    "ហានិភ័យទឹកជំនន់ កត្តាចូលរួម និងគុណភាពទិន្នន័យ សម្រាប់ខេត្តទាំងប្រាំជុំវិញបឹងទន្លេសាប។",
  refresh: "ផ្ទុកឡើងវិញ",
  runAssessment: "គណនាឡើងវិញ",
  running: "កំពុងគណនា...",
  loading: "កំពុងផ្ទុកការវាយតម្លៃហានិភ័យ...",
  loadingSub: "កំពុងភ្ជាប់ទៅ API ខាងក្រោយ",
  errorTitle: "មិនអាចផ្ទុកការវាយតម្លៃហានិភ័យបានទេ",
  tryAgain: "ព្យាយាមម្តងទៀត",
  emptyTitle: "មិនមានការវាយតម្លៃហានិភ័យទេ",
  emptyBody:
    "ប្រព័ន្ធខាងក្រោយមិនបានបញ្ជូនការវាយតម្លៃមកទេ។ សូមពិនិត្យមូលដ្ឋានទិន្នន័យ និង API /risk/assessments។",
  staleNotice:
    "ការវាយតម្លៃនេះចាស់ {age} ហើយ។ សូមចុច «គណនាឡើងវិញ» ដើម្បីប្រើទិន្នន័យអាកាសធាតុ និងទន្លេថ្មីបំផុត។",

  levels: {
    low: "ទាប",
    moderate: "មធ្យម",
    high: "ខ្ពស់",
    very_high: "ខ្ពស់បំផុត",
  },

  summary: {
    highest: "ហានិភ័យខ្ពស់បំផុត",
    average: "ពិន្ទុមធ្យមនៃអាងទន្លេ",
    elevated: "ទីតាំងមានហានិភ័យខ្ពស់ឡើង",
    coverage: "ការគ្របដណ្តប់ទិន្នន័យមធ្យម",
    of: "ក្នុងចំណោម {n}",
  },

  scale: {
    title: "មាត្រដ្ឋានហានិភ័យ",
    low: "0 - 24",
    moderate: "25 - 49",
    high: "50 - 74",
    very_high: "75 - 100",
  },

  cards: {
    score: "ពិន្ទុហានិភ័យ",
    driver: "កត្តាសំខាន់",
    rank: "ចំណាត់ថ្នាក់",
  },

  map: { title: "ផែនទីហានិភ័យអាងទន្លេ", hint: "ជ្រើសរើសចំណុចលើផែនទី" },

  compare: {
    title: "ការប្រៀបធៀបតាមខេត្ត",
    hint: "ចុចលើរបារដើម្បីជ្រើសរើស",
  },

  detail: {
    current: "ការវាយតម្លៃហានិភ័យបច្ចុប្បន្ន",
    overall: "ពិន្ទុហានិភ័យសរុប",
    category: "កម្រិតហានិភ័យ{level}",
    driver: "កត្តាហានិភ័យចម្បង",
    whyTitle: "មូលហេតុនៃពិន្ទុនេះ",
    actionsTitle: "សកម្មភាពណែនាំ",
    assessedAt: "វាយតម្លៃនៅ",
    notAvailable: "មិនមាន",
  },

  quality: {
    title: "គុណភាពទិន្នន័យ",
    coverage: "ការគ្របដណ្តប់ទិន្នន័យ",
    coverageHelp:
      "ភាគរយនៃទម្ងន់ម៉ូដែលដែលមានទិន្នន័យប្រើបាន។ កត្តាដែលខ្វះត្រូវបានដកចេញ ហើយកត្តាដែលនៅសល់ត្រូវគណនាទម្ងន់ឡើងវិញ។",
    status: "ស្ថានភាព",
    good: "ល្អ",
    partial: "មួយផ្នែក",
    limited: "មានកំណត់",
    unknown: "មិនស្គាល់",
    freshness: "ភាពថ្មីនៃប្រភពទិន្នន័យ",
    weather: "អាកាសធាតុ និងដី",
    discharge: "លំហូរទឹកទន្លេ",
    waterLevel: "កម្រិតទឹកស្ថានីយ",
    fresh: "ថ្មី",
    stale: "ហួសកាលកំណត់",
    noData: "គ្មានទិន្នន័យ",
    ago: "{age} មុន",
    excludedTitle: "មិនបានប្រើក្នុងពិន្ទុនេះ",
    excludedBody:
      "{names} មិនមានទិន្នន័យប្រើបាន ដូច្នេះពិន្ទុផ្អែកលើកត្តាដែលនៅសល់ប៉ុណ្ណោះ។",
  },

  factors: {
    title: "កត្តាចូលរួម",
    scoreHint: "ពិន្ទុកត្តា ក្នុងចំណោម 100",
    weight: "ទម្ងន់",
    score: "ពិន្ទុ",
    contribution: "ការចូលរួម",
    share: "ចំណែកនៃពិន្ទុសរុប",
    none: "មិនមានទិន្នន័យកត្តាចូលរួមទេ",
    noneBody: "API មិនបានបញ្ជូនព័ត៌មានកត្តាសម្រាប់ទីតាំងនេះទេ។",
    names: {
      rainfall: "ទឹកភ្លៀង",
      hydrology: "ជលសាស្ត្រ",
      soil: "សំណើមដី",
      seasonal: "រដូវកាល",
      historical: "ប្រវត្តិទឹកជំនន់",
    },
    help: {
      rainfall: "បរិមាណទឹកភ្លៀងសរុប ៣ ថ្ងៃ ៧ ថ្ងៃ និង ៣០ ថ្ងៃចុងក្រោយ។",
      hydrology: "លំហូរទឹកទន្លេ និងកម្រិតទឹកស្ថានីយ ធៀបនឹងកម្រិតប្រកាសអាសន្ន។",
      soil: "កម្រិតឆ្អែតទឹកនៃដី។",
      seasonal: "ទីតាំងក្នុងប្រតិទិនលំហូរទឹកឡើងចុះនៃទន្លេសាប។",
      historical: "ភាពញឹកញាប់នៃទឹកជំនន់កាលពីអតីតកាលនៅទីតាំងនេះ។",
    },
    details: {
      rain_3d_mm: "ភ្លៀង ៣ ថ្ងៃ",
      rain_7d_mm: "ភ្លៀង ៧ ថ្ងៃ",
      rain_30d_mm: "ភ្លៀង ៣០ ថ្ងៃ",
      discharge_m3s: "លំហូរទឹក",
      water_level_m: "កម្រិតទឹក",
      alarm_level_m: "កម្រិតអាសន្ន",
      soil_moisture_vol: "សំណើមដី",
      day_of_year: "ថ្ងៃទីក្នុងឆ្នាំ",
      source_value: "ភាពញឹកញាប់ទឹកជំនន់",
    },
  },

  method: {
    title: "របៀបគណនាពិន្ទុ",
    c1Tag: "ពិន្ទុថ្លឹងទម្ងន់",
    c1Title: "ពិន្ទុហានិភ័យ 0 - 100",
    c1Body:
      "កត្តានីមួយៗត្រូវបានដាក់ពិន្ទុពី 0 ដល់ 100 គុណនឹងទម្ងន់ ហើយបូកបញ្ចូលគ្នា។ កត្តាដែលខ្វះត្រូវបានដកចេញ ហើយទម្ងន់ដែលនៅសល់ត្រូវគណនាឡើងវិញ។",
    c2Tag: "ធាតុចូល",
    c2Title: "កត្តាហានិភ័យប្រាំ",
    c2Body:
      "ទឹកភ្លៀង (25%) ជលសាស្ត្រ (30%) សំណើមដី (15%) រដូវកាល (15%) និងប្រវត្តិទឹកជំនន់ (15%)។",
    c3Tag: "គុណភាពទិន្នន័យ",
    c3Title: "ការគ្របដណ្តប់ និងភាពថ្មី",
    c3Body:
      "ទិន្នន័យអាកាសធាតុ និងទន្លេដែលចាស់ជាង ៤៨ ម៉ោង ត្រូវចាត់ទុកថាហួសកាលកំណត់ ហើយត្រូវដកចេញ ជាជាងការស្មាន។",
    version: "កំណែម៉ូដែល",
    type: "ប្រភេទម៉ូដែល",
    disclaimer:
      "នេះជាពិន្ទុផ្អែកលើច្បាប់ មិនមែនជាប្រូបាប៊ីលីតេទឹកជំនន់ដែលបានក្រិតតាមខ្នាតទេ។ សូមប្រើរួមជាមួយការព្រមានផ្លូវការ។",
  },

  actions: {
    low: [
      "បន្តតាមដានជាប្រចាំ។",
      "ពិនិត្យការព្យាករណ៍ម្តងទៀតក្នុងការធ្វើបច្ចុប្បន្នភាពបន្ទាប់។",
    ],
    moderate: [
      "តាមដានទឹកភ្លៀង និងស្ថានភាពទន្លេជាប្រចាំ។",
      "ពិនិត្យលេខទំនាក់ទំនងឆ្លើយតបទឹកជំនន់ក្នុងតំបន់។",
    ],
    high: [
      "រៀបចំធនធានឆ្លើយតបទឹកជំនន់។",
      "ជូនដំណឹងដល់សហគមន៍ងាយរងគ្រោះ និងភូមិអណ្តែតទឹក។",
      "ពិនិត្យផ្លូវជម្លៀស និងទីជម្រក។",
    ],
    very_high: [
      "ផ្តល់អាទិភាពដល់ការឆ្លើយតបបន្ទាន់។",
      "វាយតម្លៃតម្រូវការជម្លៀសភ្លាមៗ។",
      "អនុវត្តតាមការព្រមានរបស់ គ.ជ.ប.គ (លេខ 1294)។",
    ],
  },
};

export function getRiskText(lang: RiskLang): RiskDictionary {
  return lang === "KM" ? KM : EN;
}

// ---------------------------------------------------------
// Helpers
// ---------------------------------------------------------

export function fill(
  template: string,
  values: Record<string, string | number>,
): string {
  return template.replace(/\{(\w+)\}/g, (_match, key: string) =>
    key in values ? String(values[key]) : `{${key}}`,
  );
}

export function clampPercent(value: number | null | undefined): number {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return 0;
  }

  return Math.min(100, Math.max(0, value));
}

/** "2h 15m", "3d", "12m" - or a Khmer equivalent */
export function formatAge(minutes: number, lang: RiskLang): string {
  const km = lang === "KM";

  if (!Number.isFinite(minutes) || minutes < 0) {
    return "-";
  }

  if (minutes < 60) {
    return `${Math.round(minutes)} ${km ? "នាទី" : "min"}`;
  }

  const hours = minutes / 60;

  if (hours < 48) {
    return `${hours.toFixed(hours < 10 ? 1 : 0)} ${km ? "ម៉ោង" : "h"}`;
  }

  return `${Math.round(hours / 24)} ${km ? "ថ្ងៃ" : "d"}`;
}

export function toNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  const parsed = Number(value);

  return Number.isFinite(parsed) ? parsed : null;
}

export function formatDetailValue(key: string, value: number): string {
  switch (key) {
    case "rain_3d_mm":
    case "rain_7d_mm":
    case "rain_30d_mm":
      return `${value.toFixed(1)} mm`;
    case "discharge_m3s":
      return `${Math.round(value).toLocaleString()} m³/s`;
    case "water_level_m":
    case "alarm_level_m":
      return `${value.toFixed(2)} m`;
    case "soil_moisture_vol":
      return `${(value * 100).toFixed(1)}%`;
    case "source_value":
      return value <= 1 ? `${Math.round(value * 100)}%` : value.toFixed(0);
    default:
      return String(Math.round(value * 100) / 100);
  }
}
