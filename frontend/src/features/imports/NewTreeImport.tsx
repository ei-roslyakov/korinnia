import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { Button, ErrorAlert } from "@/components/ui";
import { useCreateTree, useDeleteTreeById } from "@/features/tree/api";
import { apiFetch } from "@/lib/api";

import type { GedcomImport } from "./api";
import { treeNameFromFile } from "./treeName";

/**
 * "Import GEDCOM" next to "New tree": creates a tree named after the file, uploads the file
 * into it and opens the import preview (`?new=1`: cancelling there removes the empty tree).
 */
export function NewTreeImport() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const create = useCreateTree();
  const remove = useDeleteTreeById();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const start = async (file: File) => {
    setBusy(true);
    setError(null);
    let treeId: string | null = null;
    try {
      treeId = (await create.mutateAsync({ name: treeNameFromFile(file.name) })).id;
      const body = new FormData();
      body.append("file", file);
      const imp = await apiFetch<GedcomImport>(`/api/v1/trees/${treeId}/imports`, {
        method: "POST",
        body,
      });
      void navigate(`/trees/${treeId}/import?import=${imp.id}&new=1`);
    } catch (err) {
      setError(err);
      // The file was refused: don't leave an empty tree behind.
      if (treeId) remove.mutate(treeId);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <input
        ref={input}
        type="file"
        accept=".ged,.GED,text/plain"
        className="hidden"
        aria-label={t("imports.newTree")}
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) void start(file);
        }}
      />
      <Button variant="secondary" busy={busy} onClick={() => input.current?.click()}>
        {t("imports.newTree")}
      </Button>
      {Boolean(error) && (
        <div className="basis-full">
          <ErrorAlert error={error} />
        </div>
      )}
    </>
  );
}
