import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { Alert, Button, Card, ErrorAlert, Field, Input, Spinner } from "@/components/ui";

import { usePasswordReset, usePasswordResetInfo } from "./api";

export function ResetPasswordPage() {
  const { t } = useTranslation();
  const { token = "" } = useParams();
  const info = usePasswordResetInfo(token);
  const reset = usePasswordReset(token);
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const mismatch = repeat.length > 0 && password !== repeat;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!mismatch) reset.mutate(password);
  };

  return (
    <div className="mx-auto max-w-md py-8">
      <Card>
        <h1 className="mb-4 font-serif text-2xl font-semibold">{t("reset.title")}</h1>
        {info.isPending && <Spinner />}
        {info.isError && <Alert>{t("errors.link_invalid")}</Alert>}
        {reset.isSuccess ? (
          <div className="space-y-3">
            <Alert kind="success">{t("reset.done")}</Alert>
            <Link to="/login" className="text-leaf-700 text-sm underline">
              {t("auth.signIn")}
            </Link>
          </div>
        ) : (
          info.data && (
            <form onSubmit={onSubmit} className="space-y-4">
              <p className="text-bark-700 text-sm">
                {t("reset.forAccount", { email: info.data.email })}
              </p>
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
              <ErrorAlert error={reset.error} />
              <Button type="submit" className="w-full" busy={reset.isPending} disabled={mismatch}>
                {t("reset.submit")}
              </Button>
            </form>
          )
        )}
      </Card>
    </div>
  );
}
