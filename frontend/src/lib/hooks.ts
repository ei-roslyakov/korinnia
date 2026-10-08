import { useTranslation } from "react-i18next";

import { ApiError } from "./api";

/** Translate an API error code into a user-facing message. */
export function useErrorMessage() {
  const { t } = useTranslation();
  return (err: unknown): string => {
    if (err instanceof ApiError) {
      return t(`errors.${err.code}`, { defaultValue: t("errors.generic") });
    }
    return t("errors.network");
  };
}

export function useFormatDate() {
  const { i18n } = useTranslation();
  return (iso: string | null | undefined, withTime = true): string => {
    if (!iso) return "—";
    return new Intl.DateTimeFormat(i18n.language, {
      dateStyle: "medium",
      ...(withTime ? { timeStyle: "short" } : {}),
    }).format(new Date(iso));
  };
}

/** Bytes as "1.2 GB" in the interface language. */
export function useFormatBytes() {
  const { i18n } = useTranslation();
  return (bytes: number) => {
    const units = ["byte", "kilobyte", "megabyte", "gigabyte", "terabyte"] as const;
    let i = 0;
    let n = bytes;
    while (n >= 1024 && i < units.length - 1) {
      n /= 1024;
      i++;
    }
    return new Intl.NumberFormat(i18n.language, {
      style: "unit",
      unit: units[i],
      unitDisplay: "short",
      maximumFractionDigits: n < 10 && i > 0 ? 1 : 0,
    }).format(n);
  };
}
