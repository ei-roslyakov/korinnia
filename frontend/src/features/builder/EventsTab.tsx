import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { Button, Card, Dialog, ErrorAlert, Field, Input, Select, TextArea } from "@/components/ui";
import { PersonCombobox } from "@/features/person/PersonCombobox";
import { formatPartialDate } from "@/lib/dates";
import {
  EVENT_TYPES,
  PARTICIPANT_ROLES,
  type LifeEvent,
  type PartialDateInput as DateValue,
  type PersonDetail,
  type PlaceSummary,
} from "@/lib/genealogy";

import { useDeleteEvent, useSaveEvent } from "./api";
import { MapPicker, type LatLon } from "./MapPicker";
import { fromPartialDate, toPayload } from "./helpers";
import { PartialDateInput } from "./PartialDateInput";
import { PlaceInput } from "./PlaceInput";

/** Events other than birth/death (those are edited in the details form). */
export function EventsTab({ treeId, person }: { treeId: string; person: PersonDetail }) {
  const { t, i18n } = useTranslation();
  const del = useDeleteEvent(treeId);
  const [editing, setEditing] = useState<LifeEvent | "new" | null>(null);
  const events = person.events.filter((e) => e.type !== "birth" && e.type !== "death");

  return (
    <div className="space-y-4">
      <Button onClick={() => setEditing("new")}>+ {t("builder.events.add")}</Button>
      <ErrorAlert error={del.error} />
      {events.length === 0 && <p className="text-bark-700 text-sm">{t("person.noEvents")}</p>}
      <ul className="space-y-2">
        {events.map((ev) => (
          <li key={ev.id}>
            <Card className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-bark-700 text-sm">
                  {formatPartialDate(ev.date, t, i18n.language)}
                </div>
                <div className="font-medium">
                  {t(`eventTypes.${ev.type}`)}
                  {ev.title && `: ${ev.title}`}
                </div>
                {ev.place && <div className="text-sm">{ev.place.name}</div>}
              </div>
              <div className="flex gap-1">
                <Button variant="secondary" onClick={() => setEditing(ev)}>
                  {t("builder.edit")}
                </Button>
                <Button
                  variant="ghost"
                  className="text-red-700"
                  onClick={() =>
                    window.confirm(t("builder.events.confirmDelete")) && del.mutate(ev.id)
                  }
                >
                  {t("common.delete")}
                </Button>
              </div>
            </Card>
          </li>
        ))}
      </ul>
      {editing && (
        <EventDialog
          treeId={treeId}
          person={person}
          event={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

function EventDialog({
  treeId,
  person,
  event,
  onClose,
}: {
  treeId: string;
  person: PersonDetail;
  event: LifeEvent | null;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const save = useSaveEvent(treeId);
  const [type, setType] = useState(event?.type ?? "residence");
  const [title, setTitle] = useState(event?.title ?? "");
  const [description, setDescription] = useState(event?.description ?? "");
  const [date, setDate] = useState<DateValue | null>(fromPartialDate(event?.date));
  const [place, setPlace] = useState<PlaceSummary | null>(event?.place ?? null);
  const [cemetery, setCemetery] = useState(event?.cemetery_name ?? "");
  const [plot, setPlot] = useState(event?.burial_plot ?? "");
  const [gps, setGps] = useState<LatLon | null>(
    event?.latitude && event.longitude
      ? { lat: Number(event.latitude), lon: Number(event.longitude) }
      : null,
  );
  const [participants, setParticipants] = useState<
    { person_id: string; role: string; display_name: string }[]
  >(
    event?.participants ?? [
      { person_id: person.id, role: "principal", display_name: person.display_name },
    ],
  );

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate(
      {
        id: event?.id,
        type,
        title: title.trim() || null,
        description: description.trim() || null,
        date: toPayload(date),
        place_id: place?.id ?? null,
        cemetery_name: type === "burial" ? cemetery.trim() || null : null,
        burial_plot: type === "burial" ? plot.trim() || null : null,
        latitude: gps ? String(gps.lat) : null,
        longitude: gps ? String(gps.lon) : null,
        participants: participants.map(({ person_id, role }) => ({ person_id, role })),
      },
      { onSuccess: onClose },
    );
  };

  return (
    <Dialog
      open
      title={event ? t("builder.events.edit") : t("builder.events.add")}
      onClose={onClose}
    >
      <form onSubmit={onSubmit} className="max-h-[75vh] space-y-3 overflow-y-auto pr-1">
        <Field label={t("builder.events.type")}>
          {(id) => (
            <Select id={id} value={type} onChange={(e) => setType(e.target.value)}>
              {EVENT_TYPES.filter((x) => x !== "birth" && x !== "death").map((x) => (
                <option key={x} value={x}>
                  {t(`eventTypes.${x}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label={t("builder.events.title")}>
          {(id) => (
            <Input
              id={id}
              maxLength={300}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          )}
        </Field>
        <PartialDateInput label={t("builder.events.date")} value={date} onChange={setDate} />
        <PlaceInput
          treeId={treeId}
          label={t("builder.events.place")}
          value={place}
          onChange={setPlace}
        />
        {type === "burial" && (
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("person.cemetery")}>
              {(id) => (
                <Input id={id} value={cemetery} onChange={(e) => setCemetery(e.target.value)} />
              )}
            </Field>
            <Field label={t("person.plot")}>
              {(id) => <Input id={id} value={plot} onChange={(e) => setPlot(e.target.value)} />}
            </Field>
          </div>
        )}
        {(type === "burial" || gps) && (
          <div className="space-y-1">
            <span className="text-sm font-medium">{t("builder.events.gps")}</span>
            <MapPicker value={gps} onChange={setGps} height={200} />
            {gps && (
              <Button variant="ghost" onClick={() => setGps(null)}>
                {t("builder.events.clearGps")}
              </Button>
            )}
          </div>
        )}
        <Field label={t("builder.events.description")}>
          {(id) => (
            <TextArea
              id={id}
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          )}
        </Field>
        <div className="space-y-2">
          <span className="text-sm font-medium">{t("builder.events.participants")}</span>
          {participants.map((p, i) => (
            <div key={p.person_id} className="flex items-center gap-2 text-sm">
              <span className="flex-1">{p.display_name}</span>
              <Select
                aria-label={t("builder.events.role")}
                className="w-40"
                value={p.role}
                onChange={(e) =>
                  setParticipants(
                    participants.map((x, j) => (j === i ? { ...x, role: e.target.value } : x)),
                  )
                }
              >
                {PARTICIPANT_ROLES.map((r) => (
                  <option key={r} value={r}>
                    {t(`builder.roles.${r}`)}
                  </option>
                ))}
              </Select>
              {p.person_id !== person.id && (
                <Button
                  variant="ghost"
                  aria-label={t("common.remove")}
                  onClick={() => setParticipants(participants.filter((_, j) => j !== i))}
                >
                  ✕
                </Button>
              )}
            </div>
          ))}
          <PersonCombobox
            treeId={treeId}
            label={t("builder.events.addParticipant")}
            excludeIds={participants.map((p) => p.person_id)}
            onSelect={(p) =>
              setParticipants([
                ...participants,
                { person_id: p.id, role: "other", display_name: p.display_name },
              ])
            }
          />
        </div>
        <ErrorAlert error={save.error} />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" busy={save.isPending}>
            {t("common.save")}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
