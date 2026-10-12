import { useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router";
import remarkGfm from "remark-gfm";

import { Alert } from "@/components/ui";

import en from "./guide.en.md?raw";
import { slug } from "./slug";
import uk from "./guide.uk.md?raw";

const GUIDES: Record<string, string> = { en, uk };

function plain(children: unknown): string {
  if (typeof children === "string") return children;
  if (Array.isArray(children)) return children.map(plain).join("");
  return "";
}

/** The user guide (Ukrainian or English; other languages get the English one). */
export function HelpPage() {
  const { t, i18n } = useTranslation();
  const lang = i18n.resolvedLanguage ?? "en";
  const text = GUIDES[lang] ?? en;
  const sections = [...text.matchAll(/^## (.+)$/gm)].map((m) => m[1]!);
  const { hash } = useLocation();
  useEffect(() => {
    if (hash) document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView();
  }, [hash, lang]);

  return (
    <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[16rem_1fr]">
      <nav aria-label={t("help.contents")} className="lg:sticky lg:top-4 lg:self-start">
        <h2 className="text-bark-700 mb-2 text-xs font-semibold tracking-wide uppercase">
          {t("help.contents")}
        </h2>
        <ol className="space-y-1 text-sm">
          {sections.map((title) => (
            <li key={title}>
              <a href={`#${slug(title)}`} className="text-leaf-700 hover:underline">
                {title}
              </a>
            </li>
          ))}
        </ol>
      </nav>
      <article className="min-w-0">
        {!GUIDES[lang] && (
          <div className="mb-4">
            <Alert kind="info">{t("help.englishOnly")}</Alert>
          </div>
        )}
        <div className="[&_code]:bg-bark-100 [&_td]:border-bark-100 [&_th]:border-bark-100 [&_th]:bg-bark-50 leading-relaxed [&_code]:rounded [&_code]:px-1 [&_h1]:mb-4 [&_h1]:font-serif [&_h1]:text-3xl [&_h1]:font-semibold [&_h2]:mt-8 [&_h2]:mb-2 [&_h2]:scroll-mt-4 [&_h2]:font-serif [&_h2]:text-xl [&_h2]:font-semibold [&_h3]:mt-4 [&_h3]:font-semibold [&_li]:my-1 [&_li]:ml-5 [&_ol]:list-decimal [&_p]:my-2 [&_table]:my-3 [&_table]:text-sm [&_td]:border [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_ul]:list-disc">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            skipHtml
            components={{
              h2: ({ children }) => <h2 id={slug(plain(children))}>{children}</h2>,
            }}
          >
            {text}
          </ReactMarkdown>
        </div>
      </article>
    </div>
  );
}
