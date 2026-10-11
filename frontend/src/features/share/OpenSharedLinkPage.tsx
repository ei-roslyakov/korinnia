import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";

import { EmptyState } from "@/components/EmptyState";
import { Spinner } from "@/components/ui";

import { useOpenShareLink } from "./api";

/** /s/:token — open a share link and go to the tree it shows. */
export function OpenSharedLinkPage() {
  const { t } = useTranslation();
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const open = useOpenShareLink();
  const { mutate } = open;
  useEffect(() => {
    mutate(token, {
      onSuccess: (session) => void navigate(`/trees/${session.tree_id}`, { replace: true }),
    });
  }, [token, mutate, navigate]);

  if (open.isError) {
    return (
      <div className="mx-auto max-w-lg py-8">
        <EmptyState
          title={t("shareLinks.invalidTitle")}
          hint={t("shareLinks.invalidHint")}
          action={
            <Link to="/login" className="text-leaf-700 text-sm underline">
              {t("shareLinks.signIn")}
            </Link>
          }
        />
      </div>
    );
  }
  return (
    <div className="text-bark-700 flex items-center justify-center gap-2 py-16 text-sm">
      <Spinner /> {t("shareLinks.opening")}
    </div>
  );
}
