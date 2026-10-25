import type { Language } from "@/lib/types";

/**
 * "What's new", newest first. Add an entry when users get something they will notice; the
 * id is its date, YYYY-MM-DD, with ".2", ".3"… for a later entry on the same day (ids are
 * compared as strings). Users see the entries newer than the last one they saw, once, at
 * sign-in.
 */
export interface ChangelogEntry {
  id: string;
  items: Record<Language, string[]>;
}

export const CHANGELOG: ChangelogEntry[] = [
  {
    id: "2026-10-25.3",
    items: {
      en: [
        "When you add a photo to a person, you can choose who else is in it — their family is offered in a list. The photo then shows on their pages too.",
      ],
      uk: [
        "Додаючи фото людині, можна одразу вибрати, хто ще на ньому, — її рідні пропонуються списком. Фото з'явиться й на їхніх сторінках.",
      ],
      pl: [
        "Dodając zdjęcie osobie, możesz od razu wybrać, kto jeszcze na nim jest — jej rodzina jest podpowiadana na liście. Zdjęcie pojawi się też na ich stronach.",
      ],
    },
  },
  {
    id: "2026-10-25.2",
    items: {
      en: [
        "Creating a new place while describing a photo no longer reloads the page and loses the photo.",
      ],
      uk: [
        "Створення нового місця під час опису фото більше не перезавантажує сторінку й не губить фото.",
      ],
      pl: [
        "Tworzenie nowego miejsca podczas opisywania zdjęcia nie przeładowuje już strony i nie gubi zdjęcia.",
      ],
    },
  },
  {
    id: "2026-10-25",
    items: {
      en: [
        "Family album: every photo of the tree in one carousel, with its description above it. Open it with the Family album button next to the tree's name — a window over the tree — or on its own page with filters by person and decade.",
        "When you add photos in a person's editor, you are asked for their description right away.",
      ],
      uk: [
        "Сімейний альбом: усі фото родоводу в одній каруселі, з описом над кожним. Відкрийте його кнопкою «Сімейний альбом» поруч із назвою родоводу — у вікні над деревом — або на окремій сторінці з фільтрами за людиною й десятиліттям.",
        "Додаючи фото в редакторі людини, ви одразу можете їх описати.",
      ],
      pl: [
        "Album rodzinny: wszystkie zdjęcia drzewa w jednej karuzeli, z opisem nad każdym. Otwórz go przyciskiem „Album rodzinny” obok nazwy drzewa — w oknie nad drzewem — albo na osobnej stronie z filtrami według osoby i dekady.",
        "Dodając zdjęcia w edytorze osoby, od razu możesz je opisać.",
      ],
    },
  },
  {
    id: "2026-10-22",
    items: {
      en: ["Names and years on the tree keep the same size while you zoom."],
      uk: ["Імена й роки на дереві більше не змінюють розміру під час масштабування."],
      pl: ["Imiona i lata na drzewie nie zmieniają już rozmiaru podczas powiększania."],
    },
  },
  {
    id: "2026-10-18",
    items: {
      en: [
        "Korinnia is now free software under the AGPL-3.0 licence. The footer links the licence and the source code.",
      ],
      uk: [
        "Korinnia тепер вільне програмне забезпечення під ліцензією AGPL-3.0. Унизу сторінки є посилання на ліцензію та вихідний код.",
      ],
      pl: [
        "Korinnia jest teraz wolnym oprogramowaniem na licencji AGPL-3.0. Stopka zawiera odnośniki do licencji i kodu źródłowego.",
      ],
    },
  },
  {
    id: "2026-10-15.2",
    items: {
      en: [
        "Names and years on the tree grow smoothly as you zoom out, instead of jumping in size.",
      ],
      uk: ["Імена й роки на дереві плавно більшають під час віддалення, а не стрибком."],
      pl: ["Imiona i lata na drzewie płynnie rosną podczas oddalania, zamiast skakać rozmiarem."],
    },
  },
  {
    id: "2026-10-15",
    items: {
      en: [
        "The tree shows portraits and life years again when it opens: cards switch to names only just when a very large tree is zoomed far out.",
      ],
      uk: [
        "Родовід знову відкривається з портретами й роками життя: лише ім'я картки показують тільки тоді, коли дуже великий родовід сильно віддалено.",
      ],
      pl: [
        "Drzewo znów otwiera się z portretami i latami życia: same imiona karty pokazują dopiero wtedy, gdy bardzo duże drzewo jest mocno oddalone.",
      ],
    },
  },
  {
    id: "2026-10-14",
    items: {
      en: [
        "Sessions now end after 8 hours. Two minutes before, you can choose “Stay signed in”; afterwards, enter your password in the window that appears and carry on where you were.",
        "“Try the demo” on the sign-in page: anyone can explore Korinnia with their own copy of the demo family for 30 minutes.",
      ],
      uk: [
        "Сеанс тепер завершується через 8 годин. За дві хвилини до цього можна обрати «Залишитися в системі»; після — введіть пароль у вікні, що з'явиться, і продовжуйте з того самого місця.",
        "«Спробувати демо» на сторінці входу: будь-хто може ознайомитися з Корінням на власній копії демо-родини протягом 30 хвилин.",
      ],
      pl: [
        "Sesja kończy się teraz po 8 godzinach. Dwie minuty wcześniej możesz wybrać „Pozostań zalogowany”; potem wpisz hasło w oknie, które się pojawi, i kontynuuj w tym samym miejscu.",
        "„Wypróbuj demo” na stronie logowania: każdy może poznać Korinnię na własnej kopii rodziny demo przez 30 minut.",
      ],
    },
  },
  {
    id: "2026-10-12.3",
    items: {
      en: [
        "A new theme, “Night (glass)”: a deep blue sky with soft northern lights behind frosted panels. Choose it under “Theme” at the top.",
      ],
      uk: [
        "Нова тема «Ніч (скло)»: глибоке синє небо з м'яким північним сяйвом за матовими панелями. Оберіть угорі в «Тема».",
      ],
      pl: [
        "Nowy motyw „Noc (szkło)”: głębokie niebieskie niebo z miękką zorzą polarną za matowymi panelami. Wybierz u góry w „Motyw”.",
      ],
    },
  },
  {
    id: "2026-10-12.2",
    items: {
      en: [
        "Everyone can now start their own family tree: “New tree” or “Import GEDCOM” on the tree list. You are the administrator of the trees you start, and nobody else sees them unless you share them.",
      ],
      uk: [
        "Тепер кожен може почати власний родовід: «Новий родовід» або «Імпорт GEDCOM» у списку родоводів. Ви адміністратор родоводів, які створили, і ніхто інший їх не бачить, доки ви ними не поділитеся.",
      ],
      pl: [
        "Każdy może teraz założyć własne drzewo rodzinne: „Nowe drzewo” lub „Import GEDCOM” na liście drzew. Jesteś administratorem drzew, które założysz, i nikt inny ich nie widzi, dopóki ich nie udostępnisz.",
      ],
    },
  },
  {
    id: "2026-10-12",
    items: {
      en: [
        "The app opens faster: each page now loads only when you first visit it.",
        "Two-step verification keys are now stored encrypted.",
      ],
      uk: [
        "Застосунок відкривається швидше: кожна сторінка тепер завантажується, лише коли ви вперше на неї заходите.",
        "Ключі двоетапної перевірки тепер зберігаються зашифрованими.",
      ],
      pl: [
        "Aplikacja otwiera się szybciej: każda strona ładuje się dopiero przy pierwszej wizycie.",
        "Klucze weryfikacji dwuetapowej są teraz przechowywane w postaci zaszyfrowanej.",
      ],
    },
  },
  {
    id: "2026-10-11.4",
    items: {
      en: [
        "A full user guide: “User guide” at the bottom of every page explains everything from the first sign-in to imports, sharing and administration.",
      ],
      uk: [
        "Повний посібник користувача: «Посібник» унизу кожної сторінки пояснює все — від першого входу до імпорту, спільного доступу й адміністрування.",
      ],
      pl: [
        "Pełny przewodnik użytkownika: „Przewodnik” na dole każdej strony (na razie po angielsku) wyjaśnia wszystko — od pierwszego logowania po import, udostępnianie i administrację.",
      ],
    },
  },
  {
    id: "2026-10-11.3",
    items: {
      en: [
        "Share links: in “Share”, create a link that lets relatives without an account view the tree (read-only). Choose how long it works and revoke it at any time.",
        "Large trees are faster: when zoomed far out, cards show just the name.",
      ],
      uk: [
        "Посилання для перегляду: у «Поділитися» створіть посилання, за яким рідні без облікового запису бачать родовід (лише перегляд). Оберіть, скільки воно діє, і відкличте будь-коли.",
        "Великі родоводи працюють швидше: при сильному віддаленні картки показують лише ім'я.",
      ],
      pl: [
        "Linki do podglądu: w „Udostępnij” utwórz link, przez który bliscy bez konta zobaczą drzewo (tylko podgląd). Wybierz, jak długo działa, i odwołaj go w każdej chwili.",
        "Duże drzewa działają szybciej: przy dużym oddaleniu karty pokazują tylko imię.",
      ],
    },
  },
  {
    id: "2026-10-11.2",
    items: {
      en: [
        "Export a tree to GEDCOM: “GEDCOM” in the tree's Download box gives a file that MyHeritage, Ancestry, Gramps and other programs can read — optionally without the details of living people.",
      ],
      uk: [
        "Експорт родоводу в GEDCOM: кнопка «GEDCOM» у полі «Завантажити» на дереві дає файл, який читають MyHeritage, Ancestry, Gramps та інші програми — за бажанням без даних живих людей.",
      ],
      pl: [
        "Eksport drzewa do GEDCOM: przycisk „GEDCOM” w polu „Pobierz” na drzewie daje plik, który odczytają MyHeritage, Ancestry, Gramps i inne programy — opcjonalnie bez danych żyjących osób.",
      ],
    },
  },
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
