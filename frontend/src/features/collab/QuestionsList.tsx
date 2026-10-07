import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { Badge, Button, ErrorAlert, Input } from "@/components/ui";
import type { OpenQuestion } from "@/lib/genealogy";

import { useSaveQuestion } from "./api";

/** Research questions about a person ("Where was he during 1941–1945?"). */
export function QuestionsList({
  treeId,
  personId,
  questions,
  canWrite,
}: {
  treeId: string;
  personId: string;
  questions: OpenQuestion[];
  canWrite: boolean;
}) {
  const { t } = useTranslation();
  const save = useSaveQuestion(treeId);
  const [text, setText] = useState("");

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (text.trim())
      save.mutate({ person_id: personId, question: text.trim() }, { onSuccess: () => setText("") });
  };

  return (
    <div className="space-y-2 text-sm">
      <ErrorAlert error={save.error} />
      {questions.length === 0 && <p className="text-bark-700">{t("collab.questions.none")}</p>}
      <ul className="space-y-1">
        {questions.map((q) => (
          <li key={q.id} className="flex flex-wrap items-center gap-2">
            <Badge tone={q.status === "open" ? "amber" : "green"}>
              {t(`collab.questions.${q.status}`)}
            </Badge>
            <span className={q.status === "resolved" ? "text-bark-700 line-through" : ""}>
              {q.question}
            </span>
            {q.resolution && <span className="text-bark-700">→ {q.resolution}</span>}
            {canWrite && (
              <button
                type="button"
                className="text-leaf-700 text-xs underline"
                onClick={() => {
                  if (q.status === "open") {
                    const resolution =
                      window.prompt(t("collab.questions.resolutionPrompt")) ?? undefined;
                    if (resolution !== undefined)
                      save.mutate({ id: q.id, status: "resolved", resolution: resolution || null });
                  } else {
                    save.mutate({ id: q.id, status: "open" });
                  }
                }}
              >
                {q.status === "open" ? t("collab.questions.resolve") : t("collab.questions.reopen")}
              </button>
            )}
          </li>
        ))}
      </ul>
      {canWrite && (
        <form onSubmit={onSubmit} className="flex gap-2">
          <Input
            aria-label={t("collab.questions.add")}
            placeholder={t("collab.questions.placeholder")}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <Button type="submit" busy={save.isPending} disabled={!text.trim()}>
            {t("collab.questions.add")}
          </Button>
        </form>
      )}
    </div>
  );
}
