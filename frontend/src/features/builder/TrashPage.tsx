import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { Badge, Button, Card, ErrorAlert, PageHeader, Spinner } from "@/components/ui";
import { useFormatDate } from "@/lib/hooks";

import { useRestoreFromTrash, useTrash } from "./api";

export function TrashPage() {
  const { t } = useTranslation();
  const { treeId = "" } = useParams();
  const formatDate = useFormatDate();
  const trash = useTrash(treeId);
  const restore = useRestoreFromTrash(treeId);

  return (
    <div className="mx-auto max-w-3xl">
      <Link to={`/trees/${treeId}?mode=edit`} className="text-leaf-700 text-sm underline">
        ← {t("person.backToTree")}
      </Link>
      <PageHeader title={t("builder.trash.title")} />
      <p className="text-bark-700 mb-4 text-sm">{t("builder.trash.hint")}</p>
      {trash.isPending && <Spinner />}
      <ErrorAlert error={trash.error ?? restore.error} />
      {trash.data?.length === 0 && (
        <p className="text-bark-700 text-sm">{t("builder.trash.empty")}</p>
      )}
      <ul className="space-y-2">
        {trash.data?.map((item) => (
          <li key={item.entity_id}>
            <Card className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <Badge>{t(`builder.trash.types.${item.entity_type}`)}</Badge>
                  <span className="font-medium">{item.label}</span>
                </div>
                <div className="text-bark-700 text-xs">
                  {formatDate(item.deleted_at)}
                  {item.deleted_by && ` · ${item.deleted_by}`}
                  {item.batch_size > 1 &&
                    ` · ${t("builder.trash.batch", { count: item.batch_size })}`}
                </div>
              </div>
              <Button
                variant="secondary"
                busy={restore.isPending && restore.variables?.entity_id === item.entity_id}
                onClick={() => restore.mutate(item)}
              >
                {t("builder.trash.restore")}
              </Button>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
