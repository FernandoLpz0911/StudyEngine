import katex from "katex";
import "katex/dist/katex.min.css";

/** Render text whose math fragments are delimited by `$...$` (KaTeX).
 *
 * The backend wraps generator math in `$...$` and escapes literal currency as
 * `\$`. We split on unescaped `$`: odd segments are math, even segments are plain
 * text (with `\$` unescaped back to `$`). Invalid LaTeX renders as-is rather than
 * throwing. */
export default function Math({ children }: { children?: string | null }) {
  const text = children ?? "";
  const parts = text.split(/(?<!\\)\$/);
  return (
    <span>
      {parts.map((p, i) =>
        i % 2 === 1 ? (
          <span
            key={i}
            dangerouslySetInnerHTML={{
              __html: katex.renderToString(p, { throwOnError: false }),
            }}
          />
        ) : (
          <span key={i}>{p.replace(/\\\$/g, "$")}</span>
        ),
      )}
    </span>
  );
}
