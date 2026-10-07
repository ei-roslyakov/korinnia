import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { Badge, Card, ErrorAlert, PageHeader, Spinner } from "@/components/ui";
import { atLeast } from "@/lib/types";

import { useTree } from "./api";

/** Tree landing page. The interactive canvas replaces the placeholder in phase 4. */
export function TreeHomePage() {
  const { t } = useTranslation();
  const { treeId = "" } = useParams();
  const tree = useTree(treeId);

  if (tree.isPending) return <Spinner />;
  if (tree.error) return <ErrorAlert error={tree.error} />;
  const data = tree.data;

  return (
    <div className="space-y-6">
      <PageHeader
        title={data.name}
        actions={
          atLeast(data.my_role, "admin") && (
            <>
              <Link
                to={`/trees/${data.id}/members`}
                className="border-bark-100 hover:bg-bark-50 rounded-md border bg-white px-3 py-1.5 text-sm"
              >
                {t("members.title")}
              </Link>
              <Link
                to={`/trees/${data.id}/audit`}
                className="border-bark-100 hover:bg-bark-50 rounded-md border bg-white px-3 py-1.5 text-sm"
              >
                {t("audit.title")}
              </Link>
            </>
          )
        }
      />
      <div className="text-bark-700 flex items-center gap-2 text-sm">
        {t("trees.yourRole")} <Badge>{t(`roles.${data.my_role}`)}</Badge>
      </div>
      {data.description && <p className="text-bark-700 whitespace-pre-line">{data.description}</p>}
      <Card>
        <p className="text-bark-700">{t("home.comingSoon")}</p>
      </Card>
    </div>
  );
}
