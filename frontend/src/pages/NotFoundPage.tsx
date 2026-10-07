import { useTranslation } from "react-i18next";
import { Link } from "react-router";

export function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <div className="space-y-4">
      <h1 className="font-serif text-2xl font-semibold">{t("notFound.title")}</h1>
      <Link to="/" className="text-leaf-700 underline">
        {t("notFound.back")}
      </Link>
    </div>
  );
}
