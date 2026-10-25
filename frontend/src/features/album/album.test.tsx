import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";
import i18n from "@/i18n";
import { Lightbox } from "@/features/media/Lightbox";
import type { MediaItem } from "@/lib/genealogy";
import { halyna, mediaItem, smallGraph, year } from "@/test/fixtures";
import { json, ME, mockApi } from "@/test/mockApi";
import { renderWithProviders } from "@/test/render";

import { AlbumCarousel, AUTOPLAY_MS } from "./AlbumCarousel";

vi.mock("@/features/tree/canvas/TreeCanvas", () => ({
  TreeCanvas: () => <div data-testid="canvas" />,
}));

/** Embla measures real layout (jsdom has none): a stand-in that moves between slides like
 *  Embla does and reports it with "select", as after a swipe. */
const embla = vi.hoisted(() => {
  const handlers = new Map<string, Set<() => void>>();
  const state = { index: 0, count: 0 };
  const emit = (event: string) => handlers.get(event)?.forEach((fn) => fn());
  const api = {
    selectedScrollSnap: () => state.index,
    canScrollPrev: () => state.index > 0,
    canScrollNext: () => state.index < state.count - 1,
    scrollTo: (i: number) => {
      state.index = Math.max(0, Math.min(i, state.count - 1));
      emit("select");
    },
    on: (event: string, fn: () => void) => {
      if (!handlers.has(event)) handlers.set(event, new Set());
      handlers.get(event)!.add(fn);
      return api;
    },
    off: (event: string, fn: () => void) => {
      handlers.get(event)?.delete(fn);
      return api;
    },
  };
  /** What Embla does when the viewer swipes to slide `i`. */
  const swipeTo = (i: number) => api.scrollTo(i);
  return { api, state, swipeTo, handlers };
});
vi.mock("embla-carousel-react", () => ({ default: () => [() => {}, embla.api] }));

const photos: MediaItem[] = [
  mediaItem("a1", "photo", {
    title: "Весілля",
    description: "Галина й Олександр біля церкви.",
    date: year(1946),
    place: { id: "pl1", name: "Львів" } as MediaItem["place"],
    people: [{ person_id: "p2", display_name: "Галина", region: null }],
  }),
  mediaItem("a2", "photo", {
    description: "Перший клас",
    people: [{ person_id: "p3", display_name: "Олександр Коваленко", region: null }],
  }),
  mediaItem("a3", "photo", {
    people: [
      { person_id: "p2", display_name: "Галина", region: null },
      { person_id: "p1", display_name: "Йосип Шевчук", region: null },
    ],
  }),
];

function reducedMotion(reduce: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: query.includes("reduce") ? reduce : true,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    })),
  );
}

function renderCarousel(extra: Partial<Parameters<typeof AlbumCarousel>[0]> = {}) {
  embla.state.count = photos.length;
  const onOpen = vi.fn();
  renderWithProviders(
    <AlbumCarousel
      items={photos}
      total={photos.length}
      hasMore={false}
      onNearEnd={() => {}}
      onOpen={onOpen}
      personLink={(id) => `/trees/t1/people/${id}`}
      label="Сімейний альбом"
      {...extra}
    />,
  );
  return { onOpen };
}

beforeEach(async () => {
  await i18n.changeLanguage("uk");
  embla.state.index = 0;
  embla.handlers.clear();
  reducedMotion(false);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("album carousel", () => {
  it("is a labelled region; the description is above the photo, people link below", () => {
    renderCarousel();
    const region = screen.getByRole("region", { name: "Сімейний альбом" });
    expect(region).toHaveAttribute("aria-roledescription", "карусель");
    const slide = within(screen.getByRole("group", { name: "1 з 3" }));
    const caption = slide.getByTestId("photo-caption");
    const img = slide.getByRole("img", { name: "Весілля" });
    expect(caption.compareDocumentPosition(img) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(caption).getByText("Весілля").tagName).toBe("STRONG");
    expect(within(caption).getByText("Галина й Олександр біля церкви.")).toBeInTheDocument();
    expect(within(caption).getByText("1946 · Львів")).toBeInTheDocument();
    expect(slide.getByRole("link", { name: "Галина" })).toHaveAttribute(
      "href",
      "/trees/t1/people/p2",
    );
    // Only the shown photo and its neighbour load; thumbnails use the small preview.
    expect(document.querySelectorAll('img[src$="/web"]')).toHaveLength(2);
    expect(slide.getByRole("img")).toHaveAttribute("srcset", "/f/a1/thumb 480w, /f/a1/web 2048w");
    expect(
      screen.getByRole("button", { name: "Перейти до фото 3" }).querySelector("img"),
    ).toHaveAttribute("src", "/f/a3/thumb");
  });

  it("moves with next / previous, the arrow keys, thumbnails and a swipe", async () => {
    const { onOpen } = renderCarousel();
    const status = () => screen.getByText(/^\d з 3$/, { selector: "span" });
    await userEvent.click(screen.getByRole("button", { name: "Наступне" }));
    expect(status()).toHaveTextContent("2 з 3");
    expect(screen.getByRole("group", { name: "2 з 3" })).not.toHaveAttribute("inert");
    expect(screen.getByRole("group", { name: "1 з 3" })).toHaveAttribute("inert");
    expect(screen.getByRole("img", { name: "Перший клас" })).toBeInTheDocument();

    fireEvent.keyDown(screen.getByRole("button", { name: "Наступне" }), { key: "ArrowLeft" });
    expect(status()).toHaveTextContent("1 з 3");
    await userEvent.click(screen.getByRole("button", { name: "Перейти до фото 3" }));
    expect(status()).toHaveTextContent("3 з 3");
    expect(screen.getByRole("button", { name: "Перейти до фото 3" })).toHaveAttribute(
      "aria-current",
      "true",
    );
    // No people, no title: the alt text names who is in the photo.
    expect(screen.getByRole("img", { name: "Фото: Галина, Йосип Шевчук" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Наступне" })).toBeDisabled();

    act(() => embla.swipeTo(1));
    expect(status()).toHaveTextContent("2 з 3");
    await userEvent.click(screen.getByRole("img", { name: "Перший клас" }));
    expect(onOpen).toHaveBeenCalledWith(1);
  });

  it("asks for more photos near the end of what is loaded", async () => {
    const onNearEnd = vi.fn();
    renderCarousel({ hasMore: true, total: 40, onNearEnd });
    expect(screen.getByText("1 з 40")).toBeInTheDocument();
    // Three loaded, so the first is already near the end.
    expect(onNearEnd).toHaveBeenCalled();
  });

  it("plays a slideshow that pauses on hover", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    renderCarousel();
    fireEvent.click(screen.getByRole("button", { name: /Запустити показ/ }));
    act(() => vi.advanceTimersByTime(AUTOPLAY_MS + 10));
    expect(embla.state.index).toBe(1);
    fireEvent.mouseEnter(screen.getByRole("group", { name: "2 з 3" }).parentElement!);
    act(() => vi.advanceTimersByTime(AUTOPLAY_MS * 2));
    expect(embla.state.index).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: /Зупинити показ/ }));
  });

  it("has no slideshow when the system asks for reduced motion", () => {
    reducedMotion(true);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    renderCarousel();
    expect(screen.queryByRole("button", { name: /Запустити показ/ })).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(AUTOPLAY_MS * 3));
    expect(embla.state.index).toBe(0);
  });
});

describe("lightbox", () => {
  it("shows the description above the image and follows a swipe", () => {
    const onIndex = vi.fn();
    renderWithProviders(
      <Lightbox
        items={photos}
        index={0}
        total={40}
        onIndex={onIndex}
        onClose={() => {}}
        personLink={(id) => `/p/${id}`}
      />,
    );
    const box = within(screen.getByRole("dialog"));
    expect(box.getByText("1 / 40")).toBeInTheDocument();
    const caption = box.getByTestId("photo-caption");
    const img = box.getByRole("img", { name: "Весілля" });
    expect(caption.compareDocumentPosition(img) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(caption).getByText("Галина й Олександр біля церкви.")).toBeInTheDocument();

    const stage = box.getByTestId("lightbox-stage");
    fireEvent.pointerDown(stage, { clientX: 300, clientY: 200 });
    fireEvent.pointerUp(stage, { clientX: 120, clientY: 210 });
    expect(onIndex).toHaveBeenCalledWith(1);
    // A tap or a vertical move is not a swipe.
    fireEvent.pointerDown(stage, { clientX: 300, clientY: 100 });
    fireEvent.pointerUp(stage, { clientX: 260, clientY: 400 });
    expect(onIndex).toHaveBeenCalledTimes(1);
  });
});

describe("album on the tree page", () => {
  function api(album: MediaItem[], role = "viewer") {
    const calls: string[] = [];
    mockApi({
      "GET /api/v1/auth/me": () => json(ME),
      "GET /api/v1/trees/t1": () =>
        json({ id: "t1", name: "Родина", description: null, my_role: role }),
      "GET /api/v1/trees/t1/graph": () => json(smallGraph),
      "GET /api/v1/trees/t1/persons/p2": () => json(halyna),
      "GET /api/v1/trees/t1/album": ({ url }) => {
        calls.push(url);
        const items = url.includes("person_id=p2")
          ? album.filter((m) => m.people.some((p) => p.person_id === "p2"))
          : album;
        return json({ items, total: items.length, limit: 24, offset: 0, decades: [1940] });
      },
    });
    return calls;
  }

  it("opens in a popup only when asked; Esc closes it and focus goes back", async () => {
    api(photos);
    renderWithProviders(<App />, { route: "/trees/t1" });
    const button = await screen.findByRole("button", { name: /Сімейний альбом/ });
    expect(button).toHaveAttribute("aria-haspopup", "dialog");
    await waitFor(() => expect(button).toHaveTextContent("3"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByTestId("canvas")).toBeInTheDocument();

    await userEvent.click(button);
    const popup = await screen.findByRole("dialog", { name: "Сімейний альбом" });
    expect(within(popup).getByRole("region", { name: "Сімейний альбом" })).toBeInTheDocument();
    expect(within(popup).getByRole("link", { name: /Показати всі/ })).toHaveAttribute(
      "href",
      "/trees/t1/album",
    );
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(button).toHaveFocus();
    expect(localStorage.getItem("korinnia.album.open")).toBeNull();

    await userEvent.click(button);
    await userEvent.click(await screen.findByRole("button", { name: "Закрити" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("explains where photos come from; editors get a link to the guide", async () => {
    api([], "editor");
    renderWithProviders(<App />, { route: "/trees/t1" });
    await userEvent.click(await screen.findByRole("button", { name: /Сімейний альбом/ }));
    expect(await screen.findByText(/Фото додають до людей/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Як додати фото" })).toHaveAttribute(
      "href",
      "/help#сімейний-альбом",
    );
  });

  it("opens a photo full screen; Esc closes the photo first, then the album", async () => {
    api(photos);
    renderWithProviders(<App />, { route: "/trees/t1" });
    await userEvent.click(await screen.findByRole("button", { name: /Сімейний альбом/ }));
    await userEvent.click(await screen.findByRole("img", { name: "Весілля" }));
    const photo = await screen.findByRole("dialog", { name: "Весілля" });
    expect(within(photo).getByText("1 / 3")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Весілля" })).not.toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Сімейний альбом" })).toBeInTheDocument();
  });

  it("a person in the photo: only their photos, or show them on the tree", async () => {
    const calls = api(photos);
    renderWithProviders(<App />, { route: "/trees/t1" });
    await userEvent.click(await screen.findByRole("button", { name: /Сімейний альбом/ }));
    const slide = () => within(screen.getByRole("group", { name: /^1 з / }));
    await screen.findByRole("group", { name: /^1 з / });
    await userEvent.click(slide().getByRole("button", { name: /^Галина/ }));
    await userEvent.click(screen.getByRole("button", { name: "Лише фото цієї людини" }));
    await waitFor(() => expect(calls.at(-1)).toContain("person_id=p2"));
    expect(await screen.findByText("Фото: Галина")).toBeInTheDocument();
    expect(await screen.findByText("1 з 2")).toBeInTheDocument();

    await userEvent.click(slide().getByRole("button", { name: /^Галина/ }));
    await userEvent.click(screen.getByRole("button", { name: "Показати на дереві" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(
      await screen.findByRole("complementary", { name: halyna.display_name }),
    ).toBeInTheDocument();
  });
});

describe("album page", () => {
  it("filters by person and decade, sorts, and switches to a grid", async () => {
    const calls: string[] = [];
    mockApi({
      "GET /api/v1/auth/me": () => json(ME),
      "GET /api/v1/trees/t1": () =>
        json({ id: "t1", name: "Родина", description: null, my_role: "viewer" }),
      "GET /api/v1/trees/t1/persons/p2": () => json(halyna),
      "GET /api/v1/trees/t1/album": ({ url }) => {
        calls.push(url.split("?")[1] ?? "");
        const items = url.includes("person_id=p2") ? [photos[0]!] : photos;
        return json({ items, total: items.length, limit: 24, offset: 0, decades: [1940, 1950] });
      },
    });
    renderWithProviders(<App />, { route: "/trees/t1/album?person=p2" });
    expect(await screen.findByText("1 фотографія")).toBeInTheDocument();
    expect(calls.at(-1)).toContain("person_id=p2");
    expect(await screen.findByText(halyna.display_name)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Прибрати людину" }));
    expect(await screen.findByText("3 фотографії")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Десятиліття"), "1950");
    await waitFor(() => expect(calls.at(-1)).toContain("year_from=1950&year_to=1959"));
    await userEvent.selectOptions(screen.getByLabelText("Порядок"), "newest");
    await waitFor(() => expect(calls.at(-1)).toContain("sort=newest"));
    await userEvent.click(screen.getByRole("button", { name: "Сітка" }));
    expect(screen.getAllByRole("img")).toHaveLength(3);
    expect(document.querySelector('img[src="/f/a2/thumb"]')).not.toBeNull();
  });
});
