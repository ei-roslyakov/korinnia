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
