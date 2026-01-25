import { createContext, useContext, useState, ReactNode } from 'react'

export type Language = 'de' | 'en'

const translations = {
  de: {
    // App Layout
    appName: 'Isarwasser',
    appSubtitle: 'München',
    navStory: 'Geschichte',
    navExplore: 'Erkunden',
    navRecords: 'Rekorde',
    footerSource: 'Datenquelle: Bayerisches Landesamt für Umwelt (gkd.bayern.de), Pegel 16005701 München/Isar. v1 ist ein lokaler Entwicklungs-Prototyp.',
    
    // Landing Page
    landingTitle: 'Isarwasser in München',
    landingLead: 'Eine interaktive Ansicht von Wasserstand und Wassertemperatur der Isar — von 1973 bis heute.',
    landingUpcoming: 'Demnächst',
    landingUpcomingTitle: 'Jetzt vs. 50-Jahres-Normal',
    landingUpcomingBody: 'Saisonale Perzentile mit transparenter Methodik.',
    landingExploreTitle: 'Durch die Geschichte zoomen',
    landingExploreBody: 'Navigieren, zoomen, Parameter vergleichen, Datenqualität sehen.',
    landingRecordsTitle: 'Höchst-, Tiefst- und Anomalien',
    landingRecordsBody: 'Extreme und Kontext — klar mit Quellenangabe.',
    landingStatus: 'Status',
    landingLatestDaily: 'Letzte Tageswerte',
    landingWaterLevel: 'Wasserstand',
    landingWaterTemp: 'Wassertemperatur',
    landingPercentileWindow: 'Saisonales Perzentil-Fenster (±7 Tage)',
    landingLoading: 'Lädt…',
    
    // Explore Page
    exploreTitle: 'Erkunden',
    exploreSubtitle: 'Tagesmittelwerte mit Zoom, Hover und Filter-Kontrollen.',
    exploreParameter: 'Parameter:',
    exploreQuick: 'Schnell:',
    exploreToday: 'Heute',
    exploreWeek: 'Woche',
    exploreMonth: 'Monat',
    explore1Year: '1 Jahr',
    explore5Years: '5 Jahre',
    exploreAll: 'Alle',
    exploreStart: 'Start:',
    exploreEnd: 'Ende:',
    exploreLoading: 'Lade Chart-Daten...',
    exploreNoData: 'Keine Daten für den ausgewählten Zeitraum verfügbar.',
    exploreWaterLevel: 'Wasserstand (cm)',
    exploreWaterTemp: 'Wassertemperatur (°C)',
    exploreChartType: 'Diagrammtyp:',
    exploreChartLine: 'Linie',
    exploreChartArea: 'Fläche',
    exploreChartBars: 'Balken',
    exploreChartDots: 'Punkte',
    exploreResolution: 'Auflösung:',
    exploreResolutionDaily: 'Täglich',
    exploreResolutionHourly: 'Stündlich',
    exploreResolutionRaw: '15-Min',
    
    // Records Page
    recordsTitle: 'Min./Max.',
    recordsSubtitle: 'Allzeit-Extreme aus 15-Minuten-Daten (1973 → heute).',
    recordsWaterLevel: 'Wasserstand',
    recordsWaterTemp: 'Wassertemperatur',
    recordsMinMax: 'Min / Max',
    recordsMin: 'Min',
    recordsMax: 'Max',
    recordsLoading: 'Lädt…',
    recordsViewAround: 'Zeige Umgebung →',
    recordsMethod: 'Methode',
    recordsMethodTitle: 'Transparent',
    recordsMethodBody: 'Rekorde werden aus 15-Minuten-Rohdaten berechnet (Min/Max über alle Messungen).',
    recordsMethodSource: 'Quelle: Bayerisches Landesamt für Umwelt (gkd.bayern.de). Status zeigt Datenqualität (z.B. "Geprueft" = geprüft).',
    
    // Data Missing
    dataMissingTitle: 'Daten nicht verfügbar',
    dataMissingHowToFix: 'Wie beheben',
    dataMissingRunPipeline: 'Führen Sie die Ingestion-Pipeline vom Repo-Root aus:',
    
    // Units & Formatting
    unitCm: 'cm',
    unitCelsius: '°C',
    waterLevelLabel: 'Wasserstand',
    waterTempLabel: 'Wassertemperatur',
  },
  en: {
    // App Layout
    appName: 'Isarwasser',
    appSubtitle: 'München',
    navStory: 'Story',
    navExplore: 'Explore',
    navRecords: 'Min./Max.',
    footerSource: 'Data source: Bayerisches Landesamt für Umwelt (gkd.bayern.de), Station 16005701 München/Isar. v1 is a local dev prototype.',
    
    // Landing Page
    landingTitle: 'Isarwasser in München',
    landingLead: 'An interactive view of water level and water temperature of the Isar — from 1973 to today.',
    landingUpcoming: 'Coming up',
    landingUpcomingTitle: 'Now vs 50-year normal',
    landingUpcomingBody: 'Seasonal percentiles with transparent methodology.',
    landingExploreTitle: 'Zoom through history',
    landingExploreBody: 'Brush, hover, compare parameters, see data quality.',
    landingRecordsTitle: 'Highs, lows, anomalies',
    landingRecordsBody: 'Extremes and context — clearly sourced.',
    landingStatus: 'Status',
    landingLatestDaily: 'Latest daily values',
    landingWaterLevel: 'Water level',
    landingWaterTemp: 'Water temperature',
    landingPercentileWindow: 'Seasonal percentile window (±7 days)',
    landingLoading: 'Loading…',
    
    // Explore Page
    exploreTitle: 'Explore',
    exploreSubtitle: 'Daily mean values with zoom, hover, and filter controls.',
    exploreParameter: 'Parameter:',
    exploreQuick: 'Quick:',
    exploreToday: 'Today',
    exploreWeek: 'Week',
    exploreMonth: 'Month',
    explore1Year: '1 Year',
    explore5Years: '5 Years',
    exploreAll: 'All',
    exploreStart: 'Start:',
    exploreEnd: 'End:',
    exploreLoading: 'Loading chart data...',
    exploreNoData: 'No data available for the selected date range.',
    exploreWaterLevel: 'Water level (cm)',
    exploreWaterTemp: 'Water temperature (°C)',
    exploreChartType: 'Chart type:',
    exploreChartLine: 'Line',
    exploreChartArea: 'Area',
    exploreChartBars: 'Bars',
    exploreChartDots: 'Dots',
    exploreResolution: 'Resolution:',
    exploreResolutionDaily: 'Daily',
    exploreResolutionHourly: 'Hourly',
    exploreResolutionRaw: '15-min',
    
    // Records Page
    recordsTitle: 'Min./Max.',
    recordsSubtitle: 'All-time extremes from 15-minute data (1973 → present).',
    recordsWaterLevel: 'Water level',
    recordsWaterTemp: 'Water temperature',
    recordsMinMax: 'Min / Max',
    recordsMin: 'Min',
    recordsMax: 'Max',
    recordsLoading: 'Loading…',
    recordsViewAround: 'View around this date →',
    recordsMethod: 'Method',
    recordsMethodTitle: 'Transparent',
    recordsMethodBody: 'Records are computed from 15-minute raw data (min/max across all measurements).',
    recordsMethodSource: 'Source: Bayerisches Landesamt für Umwelt (gkd.bayern.de). Status indicates data quality (e.g. "Geprueft" = checked).',
    
    // Data Missing
    dataMissingTitle: 'Data not available',
    dataMissingHowToFix: 'How to fix',
    dataMissingRunPipeline: 'Run the ingestion pipeline from the repo root:',
    
    // Units & Formatting
    unitCm: 'cm',
    unitCelsius: '°C',
    waterLevelLabel: 'Water level',
    waterTempLabel: 'Water temperature',
  },
}

type I18nContextType = {
  language: Language
  setLanguage: (lang: Language) => void
  t: typeof translations.de
}

const I18nContext = createContext<I18nContextType | undefined>(undefined)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(() => {
    const stored = localStorage.getItem('language')
    return (stored === 'en' || stored === 'de') ? stored : 'de'
  })

  const handleSetLanguage = (lang: Language) => {
    setLanguage(lang)
    localStorage.setItem('language', lang)
  }

  return (
    <I18nContext.Provider
      value={{ language, setLanguage: handleSetLanguage, t: translations[language] }}
    >
      {children}
    </I18nContext.Provider>
  )
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (!context) {
    throw new Error('useI18n must be used within I18nProvider')
  }
  return context
}

