import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { Button, ErrorAlert, TextArea } from "@/components/ui";
import { useMe } from "@/features/auth/api";
import { useFormatDate } from "@/lib/hooks";
import type { CommentItem } from "@/lib/genealogy";

import { useComments, useDeleteComment, useSaveComment } from "./api";

/** Discussion under a person, story or media item. */
export function CommentsThread({
  treeId,
  entityType,
  entityId,
  canWrite,
  canModerate,
}: {
  treeId: string;
  entityType: CommentItem["entity_type"];
  entityId: string;
  canWrite: boolean;
  canModerate: boolean;
}) {
  const { t } = useTranslation();
  const formatDate = useFormatDate();
  const me = useMe();
  const comments = useComments(treeId, entityType, entityId);
  const save = useSaveComment(treeId);
  const del = useDeleteComment(treeId);
  const [text, setText] = useState("");
  const [editing, setEditing] = useState<{ id: string; body: string } | null>(null);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    save.mutate(
      { entity_type: entityType, entity_id: entityId, body: text },
      { onSuccess: () => setText("") },
    );
  };

  return (
    <div className="space-y-3">
      <ErrorAlert error={comments.error ?? save.error ?? del.error} />
      {comments.data?.length === 0 && (
        <p className="text-bark-700 text-sm">{t("collab.comments.none")}</p>
      )}
      <ul className="space-y-2">
        {comments.data?.map((c) => {
          const mine = c.author?.id === me.data?.id;
          return (
            <li key={c.id} className="bg-bark-50 rounded-md px-3 py-2 text-sm">
              <div className="text-bark-700 flex flex-wrap items-center justify-between gap-2 text-xs">
                <span>
                  <span className="text-bark-900 font-medium">
                    {c.author?.display_name ?? t("audit.system")}
                  </span>{" "}
                  · {formatDate(c.created_at)}
                </span>
                <span className="flex gap-2">
                  {mine && (
                    <button
                      type="button"
                      className="underline"
                      onClick={() => setEditing({ id: c.id, body: c.body })}
                    >
                      {t("builder.edit")}
                    </button>
                  )}
                  {(mine || canModerate) && (
                    <button
                      type="button"
                      className="text-red-700 underline"
                      onClick={() =>
                        window.confirm(t("collab.comments.confirmDelete")) && del.mutate(c.id)
                      }
                    >
                      {t("common.delete")}
                    </button>
                  )}
                </span>
              </div>
              {editing?.id === c.id ? (
                <form
                  className="mt-1 space-y-1"
                  onSubmit={(e) => {
                    e.preventDefault();
                    save.mutate(
                      { id: c.id, body: editing.body },
                      { onSuccess: () => setEditing(null) },
                    );
                  }}
                >
                  <TextArea
                    aria-label={t("builder.edit")}
                    rows={2}
                    value={editing.body}
                    onChange={(e) => setEditing({ ...editing, body: e.target.value })}
                  />
                  <div className="flex gap-2">
                    <Button type="submit" busy={save.isPending}>
                      {t("common.save")}
                    </Button>
                    <Button variant="ghost" onClick={() => setEditing(null)}>
                      {t("common.cancel")}
                    </Button>
                  </div>
                </form>
              ) : (
                <p className="mt-1 whitespace-pre-line">{c.body}</p>
              )}
            </li>
          );
        })}
      </ul>
      {canWrite && (
        <form onSubmit={onSubmit} className="space-y-2">
          <TextArea
            aria-label={t("collab.comments.add")}
            placeholder={t("collab.comments.placeholder")}
            rows={2}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <Button type="submit" busy={save.isPending} disabled={!text.trim()}>
            {t("collab.comments.add")}
          </Button>
        </form>
      )}
    </div>
  );
}
