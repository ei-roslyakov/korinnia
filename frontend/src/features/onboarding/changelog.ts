import type { Language } from "@/lib/types";

/**
 * "What's new", newest first. Add an entry when users get something they will notice; the
 * id is its date (ids are compared as strings, so keep the YYYY-MM-DD form). Users see the
 * entries newer than the last one they saw, once, at sign-in.
 */
export interface ChangelogEntry {
  id: string;
  items: Record<Language, string[]>;
}

export const CHANGELOG: ChangelogEntry[] = [
  {
    id: "2026-10-11",
    items: {
      en: [
        "Share a tree: “Share” on the tree card or in the builder gives another user access by email — view, suggest changes, edit or manage.",
        "A short welcome guide for new users, and this “What’s new” list (both are also in the footer).",
      ],
      uk: [
        "Поділитися родоводом: кнопка «Поділитися» на картці родоводу чи в режимі редагування надає доступ іншому користувачеві за електронною поштою — переглядати, пропонувати зміни, редагувати чи керувати.",
        "Короткий вітальний посібник для нових користувачів і цей список «Що нового» (обидва також унизу сторінки).",
      ],
      pl: [
        "Udostępnianie drzewa: przycisk „Udostępnij” na karcie drzewa lub w trybie edycji daje innemu użytkownikowi dostęp po adresie e-mail — podgląd, propozycje zmian, edycja lub zarządzanie.",
        "Krótki przewodnik powitalny dla nowych użytkowników i ta lista „Co nowego” (oba także w stopce).",
      ],
    },
  },
  {
    id: "2026-10-09",
    items: {
      en: [
        "Couples are joined on the tree: rings and the wedding year for a marriage, a dashed line for partners, struck-through rings after a divorce. Hover the rings for the date and place.",
        "The demo family grew to 66 people in 7 generations, with several root families.",
        "Cards never overlap any more; others make room when you drop a card.",
      ],
      uk: [
        "Пари з'єднано на дереві: обручки й рік весілля для шлюбу, пунктир для партнерів, перекреслені обручки після розлучення. Наведіть на обручки, щоб побачити дату й місце.",
        "Демонстраційна родина виросла до 66 людей у 7 поколіннях, з кількома родовими гілками.",
        "Картки більше не накладаються: інші посуваються, коли ви кладете картку.",
      ],
      pl: [
        "Pary są połączone na drzewie: obrączki i rok ślubu dla małżeństwa, linia przerywana dla partnerów, przekreślone obrączki po rozwodzie. Najedź na obrączki, aby zobaczyć datę i miejsce.",
        "Rodzina demonstracyjna urosła do 66 osób w 7 pokoleniach, z kilkoma gałęziami rodu.",
        "Karty już się nie nakładają: inne robią miejsce, gdy upuszczasz kartę.",
      ],
    },
  },
  {
    id: "2026-10-08",
    items: {
      en: [
        "Import a GEDCOM file from MyHeritage, Ancestry, Gramps and others — with a preview and people already in the tree recognised.",
        "Download the whole tree as an image (PNG) or a PDF.",
        "Administrators: stored photos and documents are checked for damage every week.",
      ],
      uk: [
        "Імпорт файлу GEDCOM з MyHeritage, Ancestry, Gramps тощо — з попереднім переглядом і розпізнаванням людей, які вже є в родоводі.",
        "Завантаження всього дерева як зображення (PNG) або PDF.",
        "Адміністраторам: збережені фото й документи щотижня перевіряються на пошкодження.",
      ],
      pl: [
        "Import pliku GEDCOM z MyHeritage, Ancestry, Gramps i innych — z podglądem i rozpoznawaniem osób, które już są w drzewie.",
        "Pobieranie całego drzewa jako obraz (PNG) lub PDF.",
        "Administratorzy: zapisane zdjęcia i dokumenty są co tydzień sprawdzane pod kątem uszkodzeń.",
      ],
    },
  },
];

export const LATEST = CHANGELOG[0]!.id;

/** Entries the user has not seen yet (all of them if they have seen none). */
export function unseen(seen: string | null): ChangelogEntry[] {
  return CHANGELOG.filter((e) => seen === null || e.id > seen);
}
