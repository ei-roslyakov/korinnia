import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Badge, Button, ErrorAlert, Input, PageHeader, Select, Spinner } from "@/components/ui";
import { useFormatDate } from "@/lib/hooks";

import { type AdminTree, useAdminDeleteTree, useAdminTrees, useRestoreTree } from "./api";
import { Pager } from "./UsersPage";

/** Every tree on the instance; superadmins can delete any of them and restore deleted ones. */
export function AdminTreesPage() {
  const { t } = useTranslation();
  const [q, setQ] = useState("");
  const [deleted, setDeleted] = useState(false);
  const [offset, setOffset] = useState(0);
  const trees = useAdminTrees({ q: q || undefined, deleted: deleted || undefined, offset });

  return (
    <div>
      <PageHeader title={t("adminTrees.title")} />
      <div className="mb-4 flex flex-wrap gap-3">
        <Input
          type="search"
          className="max-w-xs"
          placeholder={t("adminTrees.search")}
          aria-label={t("adminTrees.search")}
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOffset(0);
          }}
        />
        <Select
          className="max-w-48"
          aria-label={t("users.status")}
          value={deleted ? "deleted" : "live"}
          onChange={(e) => {
            setDeleted(e.target.value === "deleted");
            setOffset(0);
          }}
        >
          <option value="live">{t("adminTrees.live")}</option>
          <option value="deleted">{t("adminTrees.deleted")}</option>
        </Select>
      </div>
      {trees.isPending && <Spinner />}
      <ErrorAlert error={trees.error} />
      {trees.data && trees.data.items.length === 0 && (
        <p className="text-bark-700 text-sm">{t("adminTrees.empty")}</p>
      )}
      {trees.data && trees.data.items.length > 0 && (
        <>
          <div className="border-bark-100 bg-surface overflow-x-auto rounded-lg border">
            <table className="w-full text-left text-sm">
              <thead className="border-bark-100 bg-bark-50 text-bark-700 border-b">
                <tr>
                  <th className="px-3 py-2">{t("trees.name")}</th>
                  <th className="px-3 py-2">{t("adminTrees.owner")}</th>
                  <th className="px-3 py-2">{t("adminTrees.size")}</th>
                  <th className="px-3 py-2">
                    {deleted ? t("adminTrees.deletedAt") : t("adminTrees.created")}
                  </th>
                  <th className="px-3 py-2 text-right">{t("users.actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-bark-100 divide-y">
                {trees.data.items.map((tree) => (
                  <TreeRow key={tree.id} tree={tree} />
                ))}
              </tbody>
            </table>
          </div>
          <Pager total={trees.data.total} offset={offset} limit={50} onChange={setOffset} />
        </>
      )}
    </div>
  );
}

function TreeRow({ tree }: { tree: AdminTree }) {
  const { t } = useTranslation();
  const formatDate = useFormatDate();
  const del = useAdminDeleteTree();
  const restore = useRestoreTree();
  const error = del.error ?? restore.error;

  return (
    <tr className="align-top">
      <td className="px-3 py-2">
        <div className="font-medium">
          {tree.deleted_at ? (
            tree.name
          ) : (
            <Link to={`/trees/${tree.id}`} className="text-leaf-700 hover:underline">
              {tree.name}
            </Link>
          )}{" "}
          {tree.is_demo && <Badge>{t("trees.demo")}</Badge>}
        </div>
        {error && (
          <div className="mt-2">
            <ErrorAlert error={error} />
          </div>
        )}
      </td>
      <td className="px-3 py-2">
        <div>{tree.owner_name ?? "—"}</div>
        {tree.owner_email && <div className="text-bark-700">{tree.owner_email}</div>}
      </td>
      <td className="text-bark-700 px-3 py-2">
        {t("trees.people", { count: tree.person_count })} ·{" "}
        {t("adminTrees.members", { count: tree.member_count })}
      </td>
      <td className="text-bark-700 px-3 py-2">
        {formatDate(tree.deleted_at ?? tree.created_at, false)}
      </td>
      <td className="px-3 py-2">
        <div className="flex justify-end">
          {tree.deleted_at ? (
            <Button
              variant="ghost"
              busy={restore.isPending}
              onClick={() => restore.mutate(tree.id)}
            >
              {t("adminTrees.restore")}
            </Button>
          ) : (
            <Button
              variant="ghost"
              className="text-red-700"
              busy={del.isPending}
              onClick={() => {
                if (window.confirm(t("trees.confirmDelete", { name: tree.name })))
                  del.mutate(tree.id);
              }}
            >
              {t("common.delete")}
            </Button>
          )}
        </div>
      </td>
    </tr>
  );
}
