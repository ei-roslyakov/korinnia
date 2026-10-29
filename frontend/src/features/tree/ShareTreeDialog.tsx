import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Alert, Badge, Button, Dialog, ErrorAlert, Field, Input, Select } from "@/components/ui";
import type { Role, Tree } from "@/lib/types";

import { ShareLinksSection } from "@/features/share/ShareLinksSection";

import { useAddMember, useMembers } from "./api";

const ROLES: Role[] = ["viewer", "contributor", "editor", "admin"];

/** Share a tree with another user by email (only people who already have an account). */
export function ShareTreeDialog({
  tree,
  onClose,
}: {
  tree: Pick<Tree, "id" | "name" | "living_privacy">;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const members = useMembers(tree.id);
  const add = useAddMember(tree.id);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("viewer");
  const [shared, setShared] = useState<string | null>(null);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setShared(null);
    add.mutate(
      { email: email.trim(), role, invite: false },
      {
        onSuccess: (r) => {
          setShared(r.member?.display_name ?? email);
          setEmail("");
        },
      },
    );
  };

  return (
    <Dialog open onClose={onClose} title={t("share.title", { name: tree.name })}>
      <form onSubmit={onSubmit} className="space-y-4">
        <p className="text-bark-700 text-sm">{t("share.hint")}</p>
        <Field label={t("auth.email")}>
          {(id) => (
            <Input
              id={id}
              type="email"
              required
              autoFocus
              autoComplete="off"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                add.reset();
                setShared(null);
              }}
            />
          )}
        </Field>
        <Field label={t("share.access")}>
          {(id) => (
            <Select id={id} value={role} onChange={(e) => setRole(e.target.value as Role)}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {t(`share.roles.${r}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <ErrorAlert error={add.error} />
        {shared && <Alert kind="success">{t("share.done", { name: shared })}</Alert>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {t("common.close")}
          </Button>
          <Button type="submit" busy={add.isPending} disabled={!email.trim()}>
            {t("share.submit")}
          </Button>
        </div>
      </form>

      <ShareLinksSection treeId={tree.id} privacy={tree.living_privacy} />

      {members.data && members.data.members.length > 0 && (
        <section className="border-bark-100 mt-5 border-t pt-4">
          <h3 className="mb-2 text-sm font-semibold">{t("share.who")}</h3>
          <ul className="space-y-1 text-sm">
            {members.data.members.map((m) => (
              <li key={m.user_id} className="flex items-center justify-between gap-2">
                <span className="min-w-0 truncate">
                  {m.display_name} <span className="text-bark-700 text-xs">{m.email}</span>
                </span>
                <Badge>{t(`roles.${m.role}`)}</Badge>
              </li>
            ))}
          </ul>
          <Link
            to={`/trees/${tree.id}/members`}
            className="text-leaf-700 mt-3 inline-block text-sm underline"
          >
            {t("share.manage")}
          </Link>
        </section>
      )}
    </Dialog>
  );
}
