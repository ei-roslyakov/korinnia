import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";

import {
  Alert,
  Badge,
  Button,
  Card,
  CopyField,
  ErrorAlert,
  Field,
  Input,
  PageHeader,
  Select,
  Spinner,
  TextArea,
} from "@/components/ui";
import { useFormatDate } from "@/lib/hooks";
import { useMe } from "@/features/auth/api";
import { ROLES, type Role, type Tree } from "@/lib/types";

import {
  useAddMember,
  useDeleteTree,
  useMembers,
  useRemoveMember,
  useRevokeTreeInvitation,
  useTree,
  useUpdateMember,
  useUpdateTree,
  type AddMemberResponse,
} from "./api";

export function MembersPage() {
  const { t } = useTranslation();
  const { treeId = "" } = useParams();
  const tree = useTree(treeId);

  if (tree.isPending) return <Spinner />;
  if (tree.error) return <ErrorAlert error={tree.error} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title={`${tree.data.name} — ${t("members.title")}`}
        actions={
          <Link to={`/trees/${treeId}`} className="text-leaf-700 text-sm underline">
            {t("common.back")}
          </Link>
        }
      />
      <AddMemberForm treeId={treeId} />
      <MemberList treeId={treeId} />
      <TreeSettings tree={tree.data} />
    </div>
  );
}

function AddMemberForm({ treeId }: { treeId: string }) {
  const { t } = useTranslation();
  const add = useAddMember(treeId);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("viewer");
  const [result, setResult] = useState<AddMemberResponse | null>(null);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setResult(null);
    add.mutate(
      { email, role },
      {
        onSuccess: (data) => {
          setResult(data);
          setEmail("");
        },
      },
    );
  };

  return (
    <Card>
      <form onSubmit={onSubmit} className="space-y-4">
        <h2 className="font-semibold">{t("members.add")}</h2>
        <p className="text-bark-700 text-sm">{t("members.addHint")}</p>
        <div className="grid gap-3 sm:grid-cols-[1fr_12rem_auto] sm:items-end">
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
          <Field label={t("members.role")}>
            {(id) => (
              <Select id={id} value={role} onChange={(e) => setRole(e.target.value as Role)}>
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {t(`roles.${r}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Button type="submit" busy={add.isPending}>
            {t("members.addButton")}
          </Button>
        </div>
        <p className="text-bark-700 text-xs">{t(`roleHelp.${role}`)}</p>
        <ErrorAlert error={add.error} />
        {result?.kind === "member" && <Alert kind="success">{t("members.added")}</Alert>}
        {result?.kind === "invitation" && result.url && (
          <div className="space-y-2">
            <Alert kind="success">{t("members.invited")}</Alert>
            <CopyField value={result.url} />
          </div>
        )}
      </form>
    </Card>
  );
}

function MemberList({ treeId }: { treeId: string }) {
  const { t } = useTranslation();
  const formatDate = useFormatDate();
  const me = useMe();
  const members = useMembers(treeId);
  const update = useUpdateMember(treeId);
  const remove = useRemoveMember(treeId);
  const revoke = useRevokeTreeInvitation(treeId);

  if (members.isPending) return <Spinner />;
  if (members.error) return <ErrorAlert error={members.error} />;

  return (
    <Card>
      <h2 className="mb-3 font-semibold">{t("members.current")}</h2>
      <ErrorAlert error={update.error ?? remove.error ?? revoke.error} />
      <ul className="divide-bark-100 divide-y">
        {members.data.members.map((m) => (
          <li key={m.user_id} className="flex flex-wrap items-center justify-between gap-3 py-3">
            <div>
              <div className="font-medium">
                {m.display_name} {!m.is_active && <Badge tone="red">{t("users.inactive")}</Badge>}
              </div>
              <div className="text-bark-700 text-sm">{m.email}</div>
            </div>
            <div className="flex items-center gap-2">
              <Select
                aria-label={t("members.role")}
                className="w-40"
                value={m.role}
                onChange={(e) => update.mutate({ userId: m.user_id, role: e.target.value as Role })}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {t(`roles.${r}`)}
                  </option>
                ))}
              </Select>
              <Button
                variant="ghost"
                onClick={() => {
                  const self = m.user_id === me.data?.id;
                  if (
                    window.confirm(
                      self
                        ? t("members.confirmLeave")
                        : t("members.confirmRemove", { name: m.display_name }),
                    )
                  ) {
                    remove.mutate(m.user_id);
                  }
                }}
              >
                {t("common.remove")}
              </Button>
            </div>
          </li>
        ))}
      </ul>

      {members.data.invitations.length > 0 && (
        <>
          <h3 className="mt-6 mb-2 font-semibold">{t("invitations.pending")}</h3>
          <ul className="divide-bark-100 divide-y">
            {members.data.invitations.map((inv) => (
              <li key={inv.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div>
                  <div className="font-medium">{inv.email}</div>
                  <div className="text-bark-700 text-sm">
                    {inv.role && t(`roles.${inv.role}`)} ·{" "}
                    {t("invitations.expires", { date: formatDate(inv.expires_at) })}
                  </div>
                </div>
                <Button variant="ghost" onClick={() => revoke.mutate(inv.id)}>
                  {t("invitations.revoke")}
                </Button>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  );
}

function TreeSettings({ tree }: { tree: Tree }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const me = useMe();
  const update = useUpdateTree(tree.id);
  const del = useDeleteTree(tree.id);
  const [name, setName] = useState(tree.name);
  const [description, setDescription] = useState(tree.description ?? "");

  return (
    <Card>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          update.mutate({ name, description: description || null });
        }}
      >
        <h2 className="font-semibold">{t("trees.settings")}</h2>
        <Field label={t("trees.name")}>
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
        <Field label={t("trees.description")}>
          {(id) => (
            <TextArea
              id={id}
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          )}
        </Field>
        <ErrorAlert error={update.error ?? del.error} />
        {update.isSuccess && <Alert kind="success">{t("common.saved")}</Alert>}
        <div className="flex flex-wrap justify-between gap-2">
          <Button type="submit" busy={update.isPending}>
            {t("common.save")}
          </Button>
          {me.data?.is_superadmin && (
            <Button
              variant="danger"
              busy={del.isPending}
              onClick={() => {
                if (window.confirm(t("trees.confirmDelete", { name: tree.name }))) {
                  del.mutate(undefined, { onSuccess: () => void navigate("/", { replace: true }) });
                }
              }}
            >
              {t("trees.delete")}
            </Button>
          )}
        </div>
      </form>
    </Card>
  );
}
