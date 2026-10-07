import { useTranslation } from "react-i18next";
import { Link, Outlet } from "react-router";

import { LanguageSwitcher } from "./LanguageSwitcher";

export function Layout() {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-full flex-col">
      <header className="border-bark-100 border-b bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="text-leaf-700 font-serif text-xl font-semibold">
            {t("app.name")}
          </Link>
          <LanguageSwitcher />
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
