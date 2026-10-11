import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button, Checkbox, Dialog } from "@/components/ui";

/** Download the tree as a GEDCOM file, optionally without the details of living people. */
export function GedcomExportDialog({ treeId, onClose }: { treeId: string; onClose: () => void }) {
  const { t } = useTranslation();
  const [hideLiving, setHideLiving] = useState(false);
  const href = `/api/v1/trees/${treeId}/export/gedcom${hideLiving ? "?living=false" : ""}`;
  return (
    <Dialog open title={t("gedcomExport.title")} onClose={onClose}>
      <div className="space-y-4 text-sm">
        <p>{t("gedcomExport.intro")}</p>
        <p className="text-bark-700 text-xs">{t("gedcomExport.notIncluded")}</p>
        <Checkbox
          label={t("gedcomExport.hideLiving")}
          checked={hideLiving}
          onChange={(e) => setHideLiving(e.target.checked)}
        />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          {/* The server answers with an attachment, so the page stays where it is. */}
          <a
            href={href}
            download
            onClick={() => setTimeout(onClose, 300)}
            className="bg-leaf-700 hover:bg-leaf-600 text-on-leaf inline-flex items-center rounded-md px-3 py-1.5 text-sm"
          >
            {t("gedcomExport.download")}
          </a>
        </div>
      </div>
    </Dialog>
  );
}
