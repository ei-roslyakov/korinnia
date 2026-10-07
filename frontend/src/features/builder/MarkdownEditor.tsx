import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Markdown } from "@/components/Markdown";
import { Alert, Button, TextArea } from "@/components/ui";
import { useFormatDate } from "@/lib/hooks";

import { clearDraft, readDraft, type Draft } from "./helpers";

/**
 * Markdown textarea with live preview. Unsaved text is autosaved to this browser
 * (localStorage) so a closed tab or crash never loses a long biography; when a newer
 * draft exists, the editor offers to restore it.
 */
export function MarkdownEditor({
  label,
  value,
  onChange,
  draftKey,
  rows = 10,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  draftKey: string;
  rows?: number;
}) {
  const { t } = useTranslation();
  const formatDate = useFormatDate();
  const [tab, setTab] = useState<"write" | "preview">("write");
  const [draft, setDraft] = useState<Draft | null>(() => {
    const d = readDraft(draftKey);
    return d && d.text !== value ? d : null;
  });

  useEffect(() => {
    const id = setTimeout(() => {
      try {
        localStorage.setItem(
          draftKey,
          JSON.stringify({ text: value, savedAt: new Date().toISOString() }),
        );
      } catch {
        /* storage unavailable: drafts are a convenience only */
      }
    }, 800);
    return () => clearTimeout(id);
  }, [value, draftKey]);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{label}</span>
        <div
          className="border-bark-100 inline-flex overflow-hidden rounded-md border text-xs"
          role="tablist"
        >
          {(["write", "preview"] as const).map((x) => (
            <button
              key={x}
              type="button"
              role="tab"
              aria-selected={tab === x}
              className={`px-2 py-1 ${tab === x ? "bg-leaf-700 text-white" : "bg-white"}`}
              onClick={() => setTab(x)}
            >
              {t(`builder.markdown.${x}`)}
            </button>
          ))}
        </div>
      </div>
      {draft && (
        <Alert kind="info">
          <div className="flex flex-wrap items-center gap-2">
            <span>{t("builder.markdown.draftFound", { date: formatDate(draft.savedAt) })}</span>
            <Button
              variant="secondary"
              onClick={() => {
                onChange(draft.text);
                setDraft(null);
              }}
            >
              {t("builder.markdown.restoreDraft")}
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                clearDraft(draftKey);
                setDraft(null);
              }}
            >
              {t("builder.markdown.discardDraft")}
            </Button>
          </div>
        </Alert>
      )}
      {tab === "write" ? (
        <TextArea
          aria-label={label}
          rows={rows}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="font-mono text-sm"
        />
      ) : (
        <div className="border-bark-100 min-h-24 rounded-md border bg-white p-3">
          {value.trim() ? (
            <Markdown>{value}</Markdown>
          ) : (
            <p className="text-bark-700 text-sm">{t("builder.markdown.empty")}</p>
          )}
        </div>
      )}
      <p className="text-bark-700 text-xs">{t("builder.markdown.hint")}</p>
    </div>
  );
}
