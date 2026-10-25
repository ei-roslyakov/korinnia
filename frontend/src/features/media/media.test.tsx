import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";
import i18n from "@/i18n";
import { halyna, mediaItem, smallGraph } from "@/test/fixtures";
import { json, ME, mockApi, type Handler } from "@/test/mockApi";
import { renderWithProviders } from "@/test/render";

vi.mock("@/features/tree/canvas/TreeCanvas", () => ({
  TreeCanvas: () => <div data-testid="canvas" />,
}));
vi.mock("@/features/builder/MapPicker", () => ({ MapPicker: () => <div /> }));

/** Minimal XMLHttpRequest stand-in that "uploads" and answers with a canned response. */
class FakeXHR {
  static responses: { status: number; body: unknown }[] = [];
  static sent: FormData[] = [];
  upload: {
    onprogress: ((e: { lengthComputable: boolean; loaded: number; total: number }) => void) | null;
  } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  status = 0;
  responseText = "";
  withCredentials = false;
  headers: Record<string, string> = {};
  open() {}
  setRequestHeader(k: string, v: string) {
    this.headers[k] = v;
  }
  send(body: FormData) {
    FakeXHR.sent.push(body);
    const r = FakeXHR.responses.shift() ?? { status: 201, body: {} };
    setTimeout(() => {
      this.upload.onprogress?.({ lengthComputable: true, loaded: 5, total: 10 });
      this.status = r.status;
      this.responseText = JSON.stringify(r.body);
      this.onload?.();
    }, 0);
  }
}

beforeEach(async () => {
  await i18n.changeLanguage("uk");
  document.cookie = "korinnia_csrf=x; path=/";
  FakeXHR.responses = [];
  FakeXHR.sent = [];
  vi.stubGlobal("XMLHttpRequest", FakeXHR);
});
afterEach(() => vi.unstubAllGlobals());

function api(role: string, extra: Record<string, Handler> = {}) {
  return mockApi({
    "GET /api/v1/auth/me": () => json(ME),
    "GET /api/v1/trees/t1": () =>
      json({ id: "t1", name: "Родина", description: null, my_role: role }),
    "GET /api/v1/trees/t1/graph": () => json(smallGraph),
    "GET /api/v1/trees/t1/persons/p2": () => json(halyna),
    ...extra,
  });
}

describe("media on the person page", () => {
  it("shows gallery, documents and recordings; lightbox with face tags", async () => {
    api("viewer");
    renderWithProviders(<App />, { route: "/trees/t1/people/p2" });
    expect(await screen.findByRole("heading", { name: "Фотографії" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /довідка.pdf/ })).toHaveAttribute(
      "href",
      "/f/m3/original",
    );
    expect(screen.getByText(/3.0 MB/)).toBeInTheDocument();
    expect(screen.getByText("Розповідь про війну").nextElementSibling?.tagName).toBe("AUDIO");
    expect(document.querySelector('img[src="/f/m1/thumb"]')).not.toBeNull();

    await userEvent.click(screen.getByRole("button", { name: /Весілля/ }));
    const box = within(screen.getByRole("dialog", { name: "Весілля" }));
    expect(box.getAllByRole("img")[0]).toHaveAttribute("src", "/f/m1/web");
    expect(box.getAllByRole("link", { name: "Олександр Коваленко" })[0]).toHaveAttribute(
      "href",
      "/trees/t1/people/p3",
    );
    expect(box.getByRole("link", { name: "Завантажити оригінал" })).toHaveAttribute(
      "href",
      "/f/m1/original",
    );
    await userEvent.click(box.getByLabelText("Показати імена"));
    expect(box.getAllByRole("link", { name: "Олександр Коваленко" })).toHaveLength(1); // only caption link
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("media tab in the editor", () => {
  it("uploads with progress and handles duplicates", async () => {
    let tagged: unknown;
    api("editor", {
      "POST /api/v1/trees/t1/media/m9/people": (init) => {
        tagged = JSON.parse(String(init.body));
        return json(mediaItem("m9", "photo"));
      },
    });
    FakeXHR.responses = [
      { status: 201, body: mediaItem("m5", "photo") },
      { status: 409, body: { code: "duplicate_media", media_id: "m9" } },
    ];
    renderWithProviders(<App />, { route: "/trees/t1/people/p2/edit?tab=media" });
    const input = await screen.findByLabelText("Вибрати файли");
    await userEvent.click(screen.getByLabelText("Це скани документів (не фото)"));
    await userEvent.upload(input, [
      new File(["a"], "лист.jpg", { type: "image/jpeg" }),
      new File(["b"], "same.jpg", { type: "image/jpeg" }),
    ]);
    // Describing can wait.
    for (let i = 0; i < 2; i++)
      await userEvent.click(await screen.findByRole("button", { name: "Пізніше" }));
    expect(await screen.findByText("Точно такий файл уже є в родоводі.")).toBeInTheDocument();
    const sent = FakeXHR.sent[0]!;
    expect(sent.get("person_id")).toBe("p2");
    expect(sent.get("kind")).toBe("document_scan");
    await userEvent.click(screen.getByRole("button", { name: "Пов’язати наявний файл" }));
    await waitFor(() => expect(tagged).toEqual({ person_id: "p2", region: null }));
  });

  it("asks for each new photo's description right away and saves it once uploaded", async () => {
    const patches: unknown[] = [];
    api("editor", {
      "PATCH /api/v1/trees/t1/media/m5": (init) => {
        patches.push(JSON.parse(String(init.body)));
        return json(mediaItem("m5", "photo"));
      },
    });
    FakeXHR.responses = [
      { status: 201, body: mediaItem("m5", "photo") },
      { status: 201, body: mediaItem("m6", "photo") },
    ];
    renderWithProviders(<App />, { route: "/trees/t1/people/p2/edit?tab=media" });
    await userEvent.upload(await screen.findByLabelText("Вибрати файли"), [
      new File(["a"], "весілля.jpg", { type: "image/jpeg" }),
      new File(["b"], "школа.jpg", { type: "image/jpeg" }),
    ]);
    const first = within(await screen.findByRole("dialog", { name: "Опишіть фото (1 з 2)" }));
    expect(first.getByText("весілля.jpg")).toBeInTheDocument();
    await userEvent.type(first.getByLabelText("Опис"), "Весілля Галини, 1946");
    await userEvent.type(first.getByLabelText("Назва"), "Весілля");
    await userEvent.click(first.getByRole("button", { name: "Зберегти й далі" }));
    await waitFor(() =>
      expect(patches).toEqual([{ description: "Весілля Галини, 1946", title: "Весілля" }]),
    );
    // The second one is left for later: nothing is sent for it.
    const second = within(await screen.findByRole("dialog", { name: "Опишіть фото (2 з 2)" }));
    await userEvent.click(second.getByRole("button", { name: "Пізніше" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(patches).toHaveLength(1);
  });

  it("links other family members in a new photo from the relatives dropdown", async () => {
    const tags: unknown[] = [];
    api("editor", {
      "POST /api/v1/trees/t1/media/m5/people": (init) => {
        tags.push(JSON.parse(String(init.body)));
        return json(mediaItem("m5", "photo"));
      },
    });
    FakeXHR.responses = [{ status: 201, body: mediaItem("m5", "photo") }];
    renderWithProviders(<App />, { route: "/trees/t1/people/p2/edit?tab=media" });
    await userEvent.upload(await screen.findByLabelText("Вибрати файли"), [
      new File(["a"], "сестри.jpg", { type: "image/jpeg" }),
    ]);
    const dialog = within(await screen.findByRole("dialog", { name: "Опишіть фото" }));
    // The relatives drop down before anything is typed; the person themself is already in it.
    await userEvent.click(dialog.getByRole("combobox", { name: "Оберіть людину з родоводу…" }));
    expect(dialog.getByText("Рідні")).toBeInTheDocument();
    expect(dialog.queryByRole("option", { name: /Галина/ })).not.toBeInTheDocument();
    await userEvent.click(dialog.getByRole("option", { name: /Ольга Ткачук/ }));
    const inPhoto = within(dialog.getByRole("list", { name: "Хто ще на фото" }));
    expect(inPhoto.getByText("Ольга Ткачук")).toBeInTheDocument();
    // Chosen once: not offered again.
    await userEvent.click(dialog.getByRole("combobox", { name: "Оберіть людину з родоводу…" }));
    expect(dialog.queryByRole("option", { name: /Ольга Ткачук/ })).not.toBeInTheDocument();
    await userEvent.click(dialog.getByRole("button", { name: "Зберегти" }));
    await waitFor(() => expect(tags).toEqual([{ person_id: "p4", region: null }]));
  });

  it("lists linked media and sets a portrait with a crop", async () => {
    let patch: unknown;
    api("editor", {
      "PATCH /api/v1/trees/t1/persons/p2": (init) => {
        patch = JSON.parse(String(init.body));
        return json(halyna);
      },
    });
    renderWithProviders(<App />, { route: "/trees/t1/people/p2/edit?tab=media" });
    expect(await screen.findByText("Портрет")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Зробити портретом" })[0]!);
    const dialog = within(await screen.findByRole("dialog"));
    // Face region of this person in the photo pre-fills the crop.
    expect(dialog.getByTestId("region")).toBeInTheDocument();
    await userEvent.click(dialog.getByRole("button", { name: "Зберегти" }));
    await waitFor(() =>
      expect(patch).toEqual({
        primary_photo_id: "m1",
        primary_photo_crop: { x: 0.1, y: 0.1, w: 0.3, h: 0.3 },
      }),
    );
  });
});
