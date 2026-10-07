import { useTranslation } from "react-i18next";

import { Alert, Button, Dialog, ErrorAlert, Spinner } from "@/components/ui";

import { useDeletePerson, useDeletePreview } from "./api";

export function DeletePersonDialog({
  treeId,
  personId,
  onClose,
  onDeleted,
}: {
  treeId: string;
  personId: string;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const { t } = useTranslation();
  const preview = useDeletePreview(treeId, personId, true);
  const del = useDeletePerson(treeId);
  const p = preview.data;
  return (
    <Dialog open title={t("builder.delete.title")} onClose={onClose}>
      {preview.isPending && <Spinner />}
      <ErrorAlert error={preview.error ?? del.error} />
      {p && (
        <div className="space-y-3 text-sm">
          <p>{t("builder.delete.question", { name: p.person.display_name })}</p>
          <ul className="list-disc pl-5">
            <li>{t("builder.delete.parentLinks", { count: p.parent_links })}</li>
            <li>{t("builder.delete.childLinks", { count: p.child_links })}</li>
            <li>{t("builder.delete.partnerships", { count: p.partnerships })}</li>
            <li>{t("builder.delete.events", { count: p.events })}</li>
            {p.shared_events > 0 && (
              <li>{t("builder.delete.sharedEvents", { count: p.shared_events })}</li>
            )}
          </ul>
          <Alert kind="info">{t("builder.delete.trashNote")}</Alert>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="danger"
              busy={del.isPending}
              onClick={() => {
                // mutateAsync: navigation must not depend on this dialog staying mounted.
                del.mutateAsync(personId).then(onDeleted, () => undefined);
              }}
            >
              {t("builder.delete.confirm")}
            </Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
