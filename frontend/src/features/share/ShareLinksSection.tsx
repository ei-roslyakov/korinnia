import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { Alert, Button, CopyField, ErrorAlert, Field, Input, Select } from "@/components/ui";
import { useFormatDate } from "@/lib/hooks";

import { useCreateShareLink, useRevokeShareLink, useShareLinks } from "./api";

const EXPIRY = { "7": 7, "30": 30, "365": 365, never: null } as const;
type Expiry = keyof typeof EXPIRY;

/** "Anyone with the link can view": create, copy and revoke read-only links (D98). */
export function ShareLinksSection({ treeId }: { treeId: string }) {
  const { t } = useTranslation();
  const formatDate = useFormatDate();
  const links = useShareLinks(treeId);
  const create = useCreateShareLink(treeId);
  const revoke = useRevokeShareLink(treeId);
  const [label, setLabel] = useState("");
  const [expiry, setExpiry] = useState<Expiry>("30");
  const [url, setUrl] = useState<string | null>(null);
  const active = (links.data ?? []).filter((l) => l.active);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate(
      { label: label.trim() || null, expires_in_days: EXPIRY[expiry] },
      {
        onSuccess: (r) => {
          setUrl(r.url);
          setLabel("");
        },
      },
    );
  };

  return (
    <section className="border-bark-100 mt-5 space-y-3 border-t pt-4" aria-labelledby="share-links">
      <h3 id="share-links" className="text-sm font-semibold">
        {t("shareLinks.title")}
      </h3>
      <p className="text-bark-700 text-xs">{t("shareLinks.hint")}</p>
      <form onSubmit={onSubmit} className="grid gap-2 sm:grid-cols-[1fr_auto_auto] sm:items-end">
        <Field label={t("shareLinks.label")}>
          {(id) => (
            <Input
              id={id}
              maxLength={200}
              placeholder={t("shareLinks.labelPlaceholder")}
              value={label}
              onChange={(e) => setLabel(e.target.value)}
            />
          )}
        </Field>
        <Field label={t("shareLinks.expires")}>
          {(id) => (
            <Select id={id} value={expiry} onChange={(e) => setExpiry(e.target.value as Expiry)}>
              {(Object.keys(EXPIRY) as Expiry[]).map((k) => (
                <option key={k} value={k}>
                  {t(`shareLinks.expiry.${k}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Button type="submit" variant="secondary" busy={create.isPending}>
          {t("shareLinks.create")}
        </Button>
      </form>
      <ErrorAlert error={create.error ?? revoke.error} />
      {url && (
        <Alert kind="success">
          <div className="space-y-2">
            <div>{t("shareLinks.created")}</div>
            <CopyField value={url} />
          </div>
        </Alert>
      )}
      {active.length > 0 && (
        <ul className="divide-bark-100 divide-y text-sm">
          {active.map((link) => (
            <li key={link.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <div className="min-w-0">
                <div className="truncate font-medium">{link.label || t("shareLinks.unnamed")}</div>
                <div className="text-bark-700 text-xs">
                  {link.expires_at
                    ? t("shareLinks.until", { date: formatDate(link.expires_at, false) })
                    : t("shareLinks.noExpiry")}
                  {" · "}
                  {t("shareLinks.opened", { count: link.use_count })}
                </div>
              </div>
              <Button
                variant="ghost"
                className="text-red-700"
                busy={revoke.isPending && revoke.variables === link.id}
                onClick={() => revoke.mutate(link.id)}
              >
                {t("shareLinks.revoke")}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
