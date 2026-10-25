import "@testing-library/jest-dom/vitest";
import "@/i18n";

import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

// findBy… / waitFor wait up to 3 s instead of 1 s: lazily loaded pages can take longer than a
// second to import when the machine is busy, which made tests fail at random.
configure({ asyncUtilTimeout: 3000 });

// Vitest runs without globals, so Testing Library cannot register cleanup automatically.
afterEach(() => cleanup());
