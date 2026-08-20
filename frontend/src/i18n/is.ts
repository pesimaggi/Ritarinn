/**
 * Icelandic interface strings.
 *
 * Every user-visible string lives here so the interface can be translated later
 * without hunting through components. Icelandic is the primary language and the
 * source of truth; source comments and identifiers stay in English.
 */
export const is = {
  appName: "Ritarinn",

  tabs: {
    proofread: "Yfirlestur",
    summary: "Samantekt",
    plainLanguage: "Á mannamáli",
    settings: "Stillingar",
  },

  editor: {
    placeholder: "Skrifaðu eða límdu íslenskan texta hér.",
    label: "Textareitur",
  },

  actions: {
    proofread: "Yfirlesa",
    proofreading: "Les yfir…",
    accept: "Samþykkja",
    acceptAll: "Samþykkja allt",
    reject: "Hafna",
    ignore: "Hunsa",
    copy: "Afrita",
    copied: "Afritað",
    restore: "Sýna aftur",
  },

  panel: {
    title: "Ábendingar",
    empty: "Engar ábendingar fundust.",
    emptyHint: "Skrifaðu texta og smelltu á „Yfirlesa“.",
    noneFound: "Ritarinn fann engar ábendingar í þessum texta.",
    ignoredCount: (n: number) => `${n} ${n === 1 ? "hunsuð ábending" : "hunsaðar ábendingar"}`,
    suggestion: "Tillaga",
    original: "Upprunalegur texti",
    alternatives: "Aðrir möguleikar",
    noSuggestion: "Engin sjálfvirk tillaga í boði.",
    errorCode: "Villukóði",
  },

  categories: {
    spelling: "Stafsetning",
    grammar: "Málfræði",
    punctuation: "Greinarmerki",
    style: "Málfar",
    unknown: "Annað",
  },

  severity: {
    error: "Villa",
    warning: "Ábending",
  },

  status: {
    words: (n: number) => `${n} ${n === 1 ? "orð" : "orð"}`,
    issues: (n: number) => `${n} ${n === 1 ? "ábending" : "ábendingar"}`,
    processedLocally: "Unnið staðbundið",
    analysing: "Greini texta…",
    ready: "Tilbúið",
  },

  privacy: {
    badge: "Staðbundið",
    badgeUnverified: "Óstaðfest",
    tooltip: "Textinn er unninn á þessari tölvu.\nEngin textagögn eru send í skýjaþjónustu.",
    heading: "Persónuvernd",
    engineLabel: "Yfirlestrarvél",
    runtimeLabel: "Staðbundin keyrsla",
    modelLabel: "Valið líkan",
    remoteLabel: "Ytri þjónusta",
    remoteNone: "Engin",
    bindLabel: "Bakendi hlustar á",
    originsLabel: "Leyfðar vefslóðir",
    outboundLabel: "Útgangandi tengingar",
    outboundNone: "Engar",
    notLocalWarning:
      "Uppsetningin er ekki alfarið staðbundin. Farðu yfir stillingar áður en þú vinnur með viðkvæm gögn.",
  },

  setup: {
    heading: "Málgreining",
    llmHeading: "Staðbundið gervigreindarlíkan",
    neuralHeading: "Tauganetsleiðrétting",
    ready: "tilbúið",
    notInstalled: "ekki sett upp",
    notFound: "fannst ekki",
    found: "fannst",
    noModelSelected: "Ekkert líkan valið",
    modelsAvailable: (n: number) => `${n} ${n === 1 ? "líkan" : "líkön"} tiltæk`,
  },

  generation: {
    summaryHeading: "Samantekt",
    plainLanguageHeading: "Á mannamáli",

    lengthLabel: "Lengd",
    length: {
      very_short: "Mjög stutt",
      short: "Stutt",
      medium: "Miðlungs",
      detailed: "Ítarleg",
    },

    formLabel: "Form",
    form: {
      prose: "Samfelldur texti",
      bullets: "Punktar",
    },

    audienceLabel: "Markhópur",
    audience: {
      general: "Almenningur",
      experts: "Sérfræðingar",
      managers: "Stjórnendur",
      customers: "Viðskiptavinir",
      youth: "Ungmenni",
    },

    styleLabel: "Stíll",
    style: {
      plain: "Einfalt mál",
      concise: "Hnitmiðað",
      formal: "Formlegt",
      neutral: "Hlutlaust",
      friendly: "Vinalegt",
    },

    proofreadOutput: "Lesa yfir útkomuna",
    proofreadOutputHint:
      "Ábendingar úr yfirlestri eru sýndar en aldrei notaðar sjálfkrafa á textann.",

    run: "Búa til",
    running: "Vinn…",
    cancel: "Hætta við",
    rerun: "Búa til aftur",

    resultHeading: "Tillaga",
    comparisonHeading: "Samanburður",
    showDiff: "Sýna breytingar",
    showSideBySide: "Sýna hlið við hlið",

    emptyText: "Skrifaðu eða límdu texta í Yfirlestur-flipann fyrst.",
    noModel:
      "Ekkert staðbundið líkan er valið. Samantekt og einföldun þurfa staðbundið mállíkan.",
    noRuntime:
      "Ollama fannst ekki á þessari tölvu. Samantekt og einföldun þurfa staðbundna keyrslu.",
    setupHint: "Sjá Stillingar fyrir stöðu staðbundinna líkana.",

    modelLabel: "Líkan",
    chunksLabel: (chunks: number, passes: number) =>
      chunks === 1
        ? "Unnið í einni umferð"
        : `Textanum var skipt í ${chunks} hluta og þeir sameinaðir í ${passes} umferðum`,
    elapsedLabel: (ms: number) => `${(ms / 1000).toFixed(1)} sek`,
    truncatedWarning:
      "Líkanið náði hámarkslengd og útkoman gæti verið ófullgerð. Prófaðu styttri texta.",
    issuesInOutput: (n: number) =>
      n === 1
        ? "1 ábending fannst í útkomunni"
        : `${n} ábendingar fundust í útkomunni`,
    noIssuesInOutput: "Engar ábendingar fundust í útkomunni.",
    outputNotAltered: "Textanum hér að ofan hefur ekki verið breytt.",

    acceptReplaces: "Skiptir út textanum í ritlinum. Hægt er að afturkalla.",
    unchangedRatio: (percent: number) => `${percent}% textans er óbreytt`,
  },

  errors: {
    backendUnreachable:
      "Náði ekki sambandi við bakenda Ritarans. Er hann keyrandi á 127.0.0.1?",
    proofreadFailed: "Yfirlestur mistókst.",
    generationFailed: "Textagerð mistókst.",
    generationCancelled: "Hætt var við.",
    textTooLong: "Textinn er of langur fyrir yfirlestur.",
    retry: "Reyna aftur",
  },

  attribution: {
    heading: "Byggt á íslenskri máltækni",
    body:
      "Yfirlestur Ritarans byggir á GreynirCorrect og GreynirEngine frá Miðeind ehf. " +
      "og á Beygingarlýsingu íslensks nútímamáls (BÍN) frá Stofnun Árna Magnússonar " +
      "í íslenskum fræðum.",
  },
} as const;

export type Strings = typeof is;
