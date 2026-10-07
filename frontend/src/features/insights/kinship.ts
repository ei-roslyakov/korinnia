/**
 * Kinship terms ("двоюрідна сестра", "first cousin once removed", "brat dziadka") from the
 * structural answer of the relationship calculator.
 *
 * Kinship vocabularies are not translations of each other — Ukrainian numbers cousins by
 * "-юрідний" and has separate words for in-laws on the wife's and husband's side, English
 * counts "removed" generations, Polish uses descriptive forms — so each language has its own
 * small generator here instead of i18n strings.
 *
 * Every builder works for a male or female person; for an unknown gender both forms are
 * joined ("брат / сестра").
 */
import type { Gender, Relationship } from "@/lib/genealogy";

type Sex = "m" | "f";
type Lang = "uk" | "en" | "pl";

const sexOf = (g: Gender): Sex | null => (g === "male" ? "m" : g === "female" ? "f" : null);

/** Build the term for the actual sex, or "male / female" when it is unknown. */
function gendered(g: Gender, build: (s: Sex) => string): string {
  const s = sexOf(g);
  if (s) return build(s);
  const [m, f] = [build("m"), build("f")];
  return m === f ? m : `${m} / ${f}`;
}

// --- Ukrainian --------------------------------------------------------------------------------

const UK_DEGREE: Record<number, string> = {
  2: "двоюрідн",
  3: "троюрідн",
  4: "четвероюрідн",
  5: "п'ятиюрідн",
  6: "шестиюрідн",
  7: "семиюрідн",
  8: "восьмиюрідн",
};

function ukDegree(n: number, s: Sex): string {
  if (n <= 1) return "";
  const stem = UK_DEGREE[n] ?? `${n}-юрідн`;
  return `${stem}${s === "m" ? "ий" : "а"} `;
}

const pra = (n: number) => "пра".repeat(Math.max(0, n));

function ukAncestor(n: number, s: Sex): string {
  if (n === 1) return s === "m" ? "батько" : "мати";
  return pra(n - 2) + (s === "m" ? "дід" : "баба");
}

function ukDescendant(n: number, s: Sex): string {
  if (n === 1) return s === "m" ? "син" : "донька";
  if (n === 2) return s === "m" ? "онук" : "онука";
  return pra(n - 2) + (s === "m" ? "внук" : "внучка");
}

const UK_NOUN_GENITIVE: [string, string][] = [
  ["батько", "батька"],
  ["мати", "матері"],
  ["дід", "діда"],
  ["баба", "баби"],
  ["син", "сина"],
  ["донька", "доньки"],
  ["внук", "внука"],
  ["внучка", "внучки"],
  ["онук", "онука"],
  ["онука", "онуки"],
  ["брат", "брата"],
  ["сестра", "сестри"],
  ["дядько", "дядька"],
  ["тітка", "тітки"],
  ["племінник", "племінника"],
  ["племінниця", "племінниці"],
];

/** Genitive of a generated term, for "дружина двоюрідного брата"; null if unsupported. */
export function ukGenitive(term: string): string | null {
  if (/[(/]/.test(term)) return null;
  const words = term.split(" ");
  const noun = words.pop()!;
  // Longest suffix first, so "онука" is not read as "онук" + "а".
  const hit = [...UK_NOUN_GENITIVE]
    .sort((x, y) => y[0].length - x[0].length)
    .find(([nom]) => noun.endsWith(nom));
  if (!hit) return null;
  const adjectives = words.map((w) => w.replace(/ий$/, "ого").replace(/а$/, "ої"));
  return [...adjectives, noun.slice(0, noun.length - hit[0].length) + hit[1]].join(" ");
}

function ukBlood(up: number, down: number, s: Sex, half: boolean, sharedParent: Sex | null) {
  if (down === 0) return ukAncestor(up, s);
  if (up === 0) return ukDescendant(down, s);
  if (up === 1 && down === 1) {
    const base = s === "m" ? "брат" : "сестра";
    if (!half) return base;
    if (!sharedParent) return `${base} (по одному з батьків)`;
    const adj = sharedParent === "m" ? "єдинокровн" : "єдиноутробн";
    return `${adj}${s === "m" ? "ий" : "а"} ${base}`;
  }
  let term: string;
  if (up === down) {
    term = ukDegree(up, s) + (s === "m" ? "брат" : "сестра");
  } else if (up > down) {
    const g = up - down;
    const base =
      g === 1 ? (s === "m" ? "дядько" : "тітка") : pra(g - 2) + (s === "m" ? "дід" : "баба");
    term = ukDegree(g === 1 ? down : down + 1, s) + base;
  } else {
    const g = down - up;
    const base =
      g === 1
        ? s === "m"
          ? "племінник"
          : "племінниця"
        : g === 2
          ? s === "m"
            ? "онук"
            : "онука"
          : pra(g - 2) + (s === "m" ? "внук" : "внучка");
    term = ukDegree(g === 1 ? up : up + 1, s) + base;
  }
  return half ? `${term} (по одному з батьків)` : term;
}

function uk(r: Relationship): string {
  const shared = r.path[1] ? sexOf(r.path[1].person.gender) : null;
  const b = r.b.gender;
  switch (r.kind) {
    case "same":
      return "та сама людина";
    case "partner":
      return gendered(b, (s) => (s === "m" ? "чоловік" : "дружина"));
    case "blood":
      return gendered(b, (s) => ukBlood(r.up!, r.down!, s, r.half, shared));
    case "in_law": {
      const [up, down] = [r.up!, r.down!];
      const aSex = sexOf(r.a.gender);
      if (r.side === "partner_relative") {
        // b is a blood relative of a's partner (r.via).
        if (up === 1 && down === 0 && aSex) {
          return gendered(b, (s) =>
            aSex === "m" ? (s === "m" ? "тесть" : "теща") : s === "m" ? "свекор" : "свекруха",
          );
        }
        if (up === 1 && down === 1 && aSex) {
          return gendered(b, (s) =>
            aSex === "m" ? (s === "m" ? "шурин" : "своячка") : s === "m" ? "дівер" : "зовиця",
          );
        }
        if (up === 0 && down === 1) return gendered(b, (s) => (s === "m" ? "пасинок" : "падчерка"));
        const via = sexOf(r.via!.gender);
        const of = via === "m" ? "чоловіка" : via === "f" ? "дружини" : "партнера";
        return gendered(b, (s) => `${ukBlood(up, down, s, r.half, null)} ${of}`);
      }
      // b is the partner of a's blood relative (r.via).
      if (up === 1 && down === 0) return gendered(b, (s) => (s === "m" ? "вітчим" : "мачуха"));
      if (down === 1 && up <= 1) return gendered(b, (s) => (s === "m" ? "зять" : "невістка"));
      // An uncle's wife is "тітка", a great-uncle's wife "двоюрідна баба", and so on.
      if (up > down && down >= 1) return gendered(b, (s) => ukBlood(up, down, s, false, null));
      const rel = gendered(r.via!.gender, (s) => ukBlood(up, down, s, false, null));
      const gen = ukGenitive(rel);
      return gendered(b, (s) => {
        const spouse = s === "m" ? "чоловік" : "дружина";
        return gen ? `${spouse} ${gen}` : `${spouse} (${rel})`;
      });
    }
    case "distant":
      return gendered(b, (s) => (s === "m" ? "далекий родич" : "далека родичка"));
    default:
      return "спорідненість не знайдено";
  }
}

// --- English ----------------------------------------------------------------------------------

const ORDINAL = ["", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth"];
const ordinal = (n: number) => ORDINAL[n] ?? `${n}th`;
const REMOVED = ["", "once", "twice", "three times"];
const removed = (n: number) => (n ? ` ${REMOVED[n] ?? `${n} times`} removed` : "");

function greats(n: number): string {
  if (n <= 0) return "";
  if (n <= 2) return "great-".repeat(n);
  return `${n}× great-`;
}

function enBlood(up: number, down: number, s: Sex, half: boolean): string {
  const h = half ? "half-" : "";
  if (down === 0) {
    if (up === 1) return s === "m" ? "father" : "mother";
    return greats(up - 2) + (s === "m" ? "grandfather" : "grandmother");
  }
  if (up === 0) {
    if (down === 1) return s === "m" ? "son" : "daughter";
    return greats(down - 2) + (s === "m" ? "grandson" : "granddaughter");
  }
  if (up === 1 && down === 1) return h + (s === "m" ? "brother" : "sister");
  if (down === 1) return h + greats(up - 2) + (s === "m" ? "uncle" : "aunt");
  if (up === 1) return h + greats(down - 2) + (s === "m" ? "nephew" : "niece");
  const degree = Math.min(up, down) - 1;
  return `${half ? "half " : ""}${ordinal(degree)} cousin${removed(Math.abs(up - down))}`;
}

function en(r: Relationship): string {
  const b = r.b.gender;
  switch (r.kind) {
    case "same":
      return "the same person";
    case "partner":
      return gendered(b, (s) => (s === "m" ? "husband" : "wife"));
    case "blood":
      return gendered(b, (s) => enBlood(r.up!, r.down!, s, r.half));
    case "in_law": {
      const [up, down] = [r.up!, r.down!];
      if (r.side === "partner_relative") {
        if (up === 1 && down === 0) return gendered(b, (s) => `${enBlood(1, 0, s, false)}-in-law`);
        if (up === 1 && down === 1) return gendered(b, (s) => `${enBlood(1, 1, s, false)}-in-law`);
        if (up === 0 && down === 1) return gendered(b, (s) => `step${enBlood(0, 1, s, false)}`);
        const whose = gendered(r.via!.gender, (s) => (s === "m" ? "husband" : "wife"));
        const owner = sexOf(r.via!.gender) ? whose : "partner";
        return gendered(b, (s) => `${owner}'s ${enBlood(up, down, s, r.half)}`);
      }
      if (up === 1 && down === 0) return gendered(b, (s) => `step${enBlood(1, 0, s, false)}`);
      if (up === 0 && down === 1) return gendered(b, (s) => `${enBlood(0, 1, s, false)}-in-law`);
      if (up === 1 && down === 1) return gendered(b, (s) => `${enBlood(1, 1, s, false)}-in-law`);
      if (down === 1 && up >= 2) return gendered(b, (s) => enBlood(up, down, s, false));
      const rel = gendered(r.via!.gender, (s) => enBlood(up, down, s, false));
      return gendered(b, (s) => `${rel}'s ${s === "m" ? "husband" : "wife"}`);
    }
    case "distant":
      return "distant relative";
    default:
      return "no relationship found";
  }
}

// --- Polish -----------------------------------------------------------------------------------

const plPra = (n: number) => "pra".repeat(Math.max(0, n));

function plAncestor(n: number, s: Sex): string {
  if (n === 1) return s === "m" ? "ojciec" : "matka";
  return plPra(n - 2) + (s === "m" ? "dziadek" : "babcia");
}

function plDescendant(n: number, s: Sex): string {
  if (n === 1) return s === "m" ? "syn" : "córka";
  return plPra(n - 2) + (s === "m" ? "wnuk" : "wnuczka");
}

function plGenitive(term: string): string | null {
  const table: [RegExp, string][] = [
    [/ojciec$/, "ojca"],
    [/matka$/, "matki"],
    [/dziadek$/, "dziadka"],
    [/babcia$/, "babci"],
    [/syn$/, "syna"],
    [/córka$/, "córki"],
    [/wnuk$/, "wnuka"],
    [/wnuczka$/, "wnuczki"],
    [/brat$/, "brata"],
    [/siostra$/, "siostry"],
  ];
  for (const [re, gen] of table) if (re.test(term)) return term.replace(re, gen);
  return null;
}

const pokolenie = (n: number) =>
  n === 1
    ? "pokolenie"
    : n % 10 >= 2 && n % 10 <= 4 && (n < 10 || n > 20)
      ? "pokolenia"
      : "pokoleń";

/** `path` lets descriptive forms name the linking relative ("brat dziadka"). */
function plBlood(r: Relationship, s: Sex): string {
  const [up, down, half] = [r.up!, r.down!, r.half];
  const przyrodni = (term: string) =>
    half ? `${s === "m" ? "przyrodni" : "przyrodnia"} ${term}` : term;
  if (down === 0) return plAncestor(up, s);
  if (up === 0) return plDescendant(down, s);
  if (up === 1 && down === 1) return przyrodni(s === "m" ? "brat" : "siostra");
  if (up === 2 && down === 1) return przyrodni(s === "m" ? "wujek" : "ciocia");
  if (down === 1) {
    // Sibling of an ancestor: "brat dziadka", "siostra prababci".
    const anc = r.path[up - 1]?.person;
    const ancTerm = gendered(anc?.gender ?? "unknown", (x) => plAncestor(up - 1, x));
    return `${przyrodni(s === "m" ? "brat" : "siostra")} ${plGenitive(ancTerm) ?? ancTerm}`;
  }
  if (up === 1) {
    const sib = sexOf(r.path[2]?.person.gender ?? "unknown");
    if (down === 2) {
      const m = s === "m" ? "bratanek" : "bratanica";
      const f = s === "m" ? "siostrzeniec" : "siostrzenica";
      return przyrodni(sib === "m" ? m : sib === "f" ? f : `${m} / ${f}`);
    }
    const sibling = sib === "m" ? "brata" : sib === "f" ? "siostry" : "rodzeństwa";
    return `${plDescendant(down - 1, s)} ${sibling}${half ? " (przyrodniego)" : ""}`;
  }
  const degree = Math.min(up, down) - 1;
  const base = (s === "m" ? "kuzyn" : "kuzynka") + (degree > 1 ? ` ${degree}. stopnia` : "");
  const diff = Math.abs(up - down);
  const age = diff
    ? `, o ${diff} ${pokolenie(diff)} ${up > down ? (s === "m" ? "starszy" : "starsza") : s === "m" ? "młodszy" : "młodsza"}`
    : "";
  return przyrodni(base) + age;
}

function pl(r: Relationship): string {
  const b = r.b.gender;
  switch (r.kind) {
    case "same":
      return "ta sama osoba";
    case "partner":
      return gendered(b, (s) => (s === "m" ? "mąż" : "żona"));
    case "blood":
      return gendered(b, (s) => plBlood(r, s));
    case "in_law": {
      const [up, down] = [r.up!, r.down!];
      const sub: Relationship = { ...r, path: r.path.slice(r.side === "partner_relative" ? 1 : 0) };
      if (r.side === "partner_relative") {
        if (up === 1 && down === 0) return gendered(b, (s) => (s === "m" ? "teść" : "teściowa"));
        if (up === 1 && down === 1)
          return gendered(b, (s) => (s === "m" ? "szwagier" : "szwagierka"));
        if (up === 0 && down === 1)
          return gendered(b, (s) => (s === "m" ? "pasierb" : "pasierbica"));
        const via = sexOf(r.via!.gender);
        const of = via === "m" ? "męża" : via === "f" ? "żony" : "partnera";
        return gendered(b, (s) => `${plBlood(sub, s)} ${of}`);
      }
      if (up === 1 && down === 0) return gendered(b, (s) => (s === "m" ? "ojczym" : "macocha"));
      if (up === 0 && down === 1) return gendered(b, (s) => (s === "m" ? "zięć" : "synowa"));
      if (up === 1 && down === 1) {
        const sib = sexOf(r.via!.gender);
        return gendered(b, (s) =>
          s === "f" && sib === "m" ? "bratowa" : s === "m" ? "szwagier" : "szwagierka",
        );
      }
      if (up === 2 && down === 1) return gendered(b, (s) => (s === "m" ? "wujek" : "ciocia"));
      const rel = gendered(r.via!.gender, (s) => plBlood({ ...sub, b: r.via! }, s));
      const gen = plGenitive(rel);
      return gendered(b, (s) => {
        const spouse = s === "m" ? "mąż" : "żona";
        return gen ? `${spouse} ${gen}` : `${spouse} (${rel})`;
      });
    }
    case "distant":
      return gendered(b, (s) => (s === "m" ? "daleki krewny" : "daleka krewna"));
    default:
      return "nie znaleziono pokrewieństwa";
  }
}

const BUILDERS: Record<Lang, (r: Relationship) => string> = { uk, en, pl };

/** The kinship term for "who is `r.b` to `r.a`", in the given UI language. */
export function kinshipTerm(r: Relationship, lang: string): string {
  const key = (lang.slice(0, 2) as Lang) in BUILDERS ? (lang.slice(0, 2) as Lang) : "en";
  return BUILDERS[key](r);
}
