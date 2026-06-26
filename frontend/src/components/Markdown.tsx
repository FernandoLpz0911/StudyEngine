import "katex/dist/katex.min.css";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";

/** Render authored teaching markdown with inline `$…$` and display `$$…$$` math.
 *
 * Used for concept theory (the LearningModel Exam P write-ups): headings, tables,
 * and KaTeX-rendered formulas. Inline generator math still uses the lighter
 * <Tex> renderer. */
export default function Markdown({ children }: { children?: string | null }) {
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
        {children ?? ""}
      </ReactMarkdown>
    </div>
  );
}
