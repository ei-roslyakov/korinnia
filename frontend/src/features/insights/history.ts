/** Major events of Ukrainian history, shown as context on the family timeline. */
export interface HistoryEvent {
  key: string;
  from: number;
  to: number;
}

export const HISTORY: HistoryEvent[] = [
  { key: "emancipation", from: 1861, to: 1861 },
  { key: "ww1", from: 1914, to: 1918 },
  { key: "revolution", from: 1917, to: 1921 },
  { key: "holodomor", from: 1932, to: 1933 },
  { key: "ww2", from: 1939, to: 1945 },
  { key: "famine1947", from: 1946, to: 1947 },
  { key: "chornobyl", from: 1986, to: 1986 },
  { key: "independence", from: 1991, to: 1991 },
  { key: "dignity", from: 2013, to: 2014 },
  { key: "invasion", from: 2022, to: 2022 },
];

/** Events starting within [first, last]. */
export function historyBetween(first: number, last: number): HistoryEvent[] {
  return HISTORY.filter((h) => h.from >= first && h.from <= last);
}
