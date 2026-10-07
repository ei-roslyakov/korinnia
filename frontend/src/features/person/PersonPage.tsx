import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { ErrorAlert } from "@/components/ui";
import { useTree } from "@/features/tree/api";
import { atLeast } from "@/lib/types";

import { usePerson } from "./api";
import { PersonView } from "./PersonView";
import { TextSkeleton } from "@/components/Skeleton";

/** Full-page view of one person (shareable link, printable). */
export function PersonPage() {
  const { t } = useTranslation();
  const { treeId = "", personId = "" } = useParams();
  const tree = useTree(treeId);
  const person = usePerson(treeId, personId);

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Link
        to={`/trees/${treeId}?person=${personId}`}
        className="text-leaf-700 text-sm underline print:hidden"
      >
        ← {t("person.backToTree")}
      </Link>
      {person.isPending && <TextSkeleton lines={6} label={t("common.loading")} />}
      <ErrorAlert error={person.error} />
      {person.data && (
        <PersonView
          person={person.data}
          personLink={(id) => `/trees/${treeId}/people/${id}`}
          showWarnings={tree.data ? atLeast(tree.data.my_role, "editor") : false}
          treeId={treeId}
          role={tree.data?.my_role}
        />
      )}
    </div>
  );
}
