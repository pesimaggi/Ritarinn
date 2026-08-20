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
    undo: "Afturkalla",
    clear: "Hreinsa texta",
    deleteLocalData: "Eyða staðbundnum gögnum",
    showIgnored: "Sýna hunsaðar ábendingar",
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

  features: {
    summaryUnavailable:
      "Samantekt krefst staðbundins mállíkans og er ekki komin í þessa útgáfu.",
    plainLanguageUnavailable:
      "Einföldun texta krefst staðbundins mállíkans og er ekki komin í þessa útgáfu.",
    neverCloud: "Ritarinn sendir aldrei texta í skýjaþjónustu í staðinn.",
    plannedFor: "Væntanlegt í útgáfu 0.2.",
  },

  errors: {
    backendUnreachable:
      "Náði ekki sambandi við bakenda Ritarans. Er hann keyrandi á 127.0.0.1?",
    proofreadFailed: "Yfirlestur mistókst.",
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
