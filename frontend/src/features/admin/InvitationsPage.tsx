import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  Alert,
  Button,
  Card,
  Checkbox,
  CopyField,
  ErrorAlert,
  Field,
  Input,
  PageHeader,
  Select,
  Spinner,
} from "@/components/ui";
import { useFormatDate } from "@/lib/hooks";
import { useTrees } from "@/features/tree/api";
import { ROLES, type Role } from "@/lib/types";

import { useCreateInvitation, useInvitations, useRevokeInvitation } from "./api";

export function InvitationsPage() {
  const { t } = useTranslation();
  const formatDate = useFormatDate();
  const invitations = useInvitations();
  const revoke = useRevokeInvitation();

  return (
    <div className="space-y-6">
      <PageHeader title={t("invitations.title")} />
      <InviteForm />
      <Card>
        <h2 className="mb-3 font-semibold">{t("invitations.pending")}</h2>
        {invitations.isPending && <Spinner />}
        <ErrorAlert error={invitations.error ?? revoke.error} />
        {invitations.data?.length === 0 && (
          <p className="text-bark-700 text-sm">{t("invitations.none")}</p>
        )}
        <ul className="divide-bark-100 divide-y">
          {invitations.data?.map((inv) => (
            <li key={inv.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div>
                <div className="font-medium">{inv.email}</div>
                <div className="text-bark-700 text-sm">
                  {inv.tree_name
                    ? `${inv.tree_name} · ${inv.role ? t(`roles.${inv.role}`) : ""}`
                    : t("users.superadmin")}
                  {" · "}
                  {t("invitations.expires", { date: formatDate(inv.expires_at) })}
                  {inv.created_by_name &&
                    ` · ${t("invitations.by", { name: inv.created_by_name })}`}
                </div>
              </div>
              <Button variant="ghost" onClick={() => revoke.mutate(inv.id)}>
                {t("invitations.revoke")}
              </Button>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function InviteForm() {
  const { t } = useTranslation();
  const trees = useTrees();
  const create = useCreateInvitation();
  const [email, setEmail] = useState("");
  const [treeId, setTreeId] = useState("");
  const [role, setRole] = useState<Role>("viewer");
  const [superadmin, setSuperadmin] = useState(false);
  const [url, setUrl] = useState<string | null>(null);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setUrl(null);
    create.mutate(
      {
        email,
        tree_id: treeId || null,
        role: treeId ? role : null,
        is_superadmin: superadmin,
      },
      {
        onSuccess: (data) => {
          setUrl(data.url);
          setEmail("");
        },
      },
    );
  };

  return (
    <Card>
      <form onSubmit={onSubmit} className="space-y-4">
        <h2 className="font-semibold">{t("invitations.new")}</h2>
        <p className="text-bark-700 text-sm">{t("invitations.hint")}</p>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label={t("auth.email")}>
            {(id) => (
              <Input
                id={id}
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            )}
          </Field>
          <Field label={t("invitations.tree")}>
            {(id) => (
              <Select id={id} value={treeId} onChange={(e) => setTreeId(e.target.value)}>
                <option value="">{t("invitations.noTree")}</option>
                {trees.data?.map((tree) => (
                  <option key={tree.id} value={tree.id}>
                    {tree.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label={t("members.role")}>
            {(id) => (
              <Select
                id={id}
                value={role}
                disabled={!treeId}
                onChange={(e) => setRole(e.target.value as Role)}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {t(`roles.${r}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
        <Checkbox
          label={t("users.superadmin")}
          checked={superadmin}
          onChange={(e) => setSuperadmin(e.target.checked)}
        />
        <ErrorAlert error={create.error} />
        {url && (
          <div className="space-y-2">
            <Alert kind="success">{t("members.invited")}</Alert>
            <CopyField value={url} />
          </div>
        )}
        <Button type="submit" busy={create.isPending} disabled={!treeId && !superadmin}>
          {t("invitations.create")}
        </Button>
      </form>
    </Card>
  );
}
