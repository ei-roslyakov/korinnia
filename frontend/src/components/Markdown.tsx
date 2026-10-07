import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Renders user-written Markdown (biographies, stories). Raw HTML is never rendered. */
export function Markdown({ children, className = "" }: { children: string; className?: string }) {
  return (
    <div
      className={`[&_a]:text-leaf-700 [&_blockquote]:border-bark-100 [&_td]:border-bark-100 [&_th]:border-bark-100 max-w-none leading-relaxed [&_a]:underline [&_blockquote]:border-l-4 [&_blockquote]:pl-3 [&_blockquote]:italic [&_h1]:mt-4 [&_h1]:font-serif [&_h1]:text-xl [&_h1]:font-semibold [&_h2]:mt-4 [&_h2]:font-serif [&_h2]:text-lg [&_h2]:font-semibold [&_h3]:mt-3 [&_h3]:font-semibold [&_li]:ml-5 [&_ol]:list-decimal [&_p]:my-2 [&_table]:my-2 [&_td]:border [&_td]:px-2 [&_th]:border [&_th]:px-2 [&_ul]:list-disc ${className}`}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          a: ({ href, children: label }) => (
            <a href={href} target="_blank" rel="noopener noreferrer nofollow">
              {label}
            </a>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
