import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";

import { Alert, Button, Card, ErrorAlert, Field, Input, Select, Spinner } from "@/components/ui";
import { SUPPORTED_LANGUAGES } from "@/i18n";
import type { Language } from "@/lib/types";

import { useAcceptInvitation, useInvitationInfo } from "./api";

export function AcceptInvitePage() {
  const { t, i18n } = useTranslation();
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const info = useInvitationInfo(token);
  const accept = useAcceptInvitation(token);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [language, setLanguage] = useState<Language>((i18n.resolvedLanguage as Language) ?? "uk");
  const mismatch = repeat.length > 0 && password !== repeat;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (mismatch) return;
    accept.mutate(
      { display_name: name, password, preferred_language: language },
      { onSuccess: () => void navigate("/", { replace: true }) },
    );
  };

  return (
    <div className="mx-auto max-w-md py-8">
      <Card>
        <h1 className="mb-4 font-serif text-2xl font-semibold">{t("invite.title")}</h1>
        {info.isPending && <Spinner />}
        {info.isError && (
          <div className="space-y-3">
            <Alert>{t("errors.link_invalid")}</Alert>
            <Link to="/login" className="text-leaf-700 text-sm underline">
              {t("auth.signIn")}
            </Link>
          </div>
        )}
        {info.data && (
          <form onSubmit={onSubmit} className="space-y-4">
            <p className="text-bark-700 text-sm">
              {info.data.tree_name
                ? t("invite.toTree", {
                    tree: info.data.tree_name,
                    role: t(`roles.${info.data.role}`),
                  })
                : t("invite.asAdmin")}
            </p>
            <Field label={t("auth.email")}>
              {(id) => <Input id={id} value={info.data.email} readOnly disabled />}
            </Field>
            <Field label={t("profile.displayName")} hint={t("invite.nameHint")}>
              {(id) => (
                <Input
                  id={id}
                  required
                  maxLength={200}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              )}
            </Field>
            <Field label={t("auth.newPassword")} hint={t("auth.passwordRules")}>
              {(id) => (
                <Input
                  id={id}
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={10}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              )}
            </Field>
            <Field label={t("auth.repeatPassword")}>
              {(id) => (
                <Input
                  id={id}
                  type="password"
                  autoComplete="new-password"
                  required
                  value={repeat}
                  onChange={(e) => setRepeat(e.target.value)}
                />
              )}
            </Field>
            {mismatch && <Alert>{t("auth.passwordsDiffer")}</Alert>}
            <Field label={t("profile.language")}>
              {(id) => (
                <Select
                  id={id}
                  value={language}
                  onChange={(e) => {
                    setLanguage(e.target.value as Language);
                    void i18n.changeLanguage(e.target.value);
                  }}
                >
                  {SUPPORTED_LANGUAGES.map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <ErrorAlert error={accept.error} />
            <Button type="submit" className="w-full" busy={accept.isPending} disabled={mismatch}>
              {t("invite.accept")}
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
}
