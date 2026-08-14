import { Fragment, type ReactNode } from "react";
import { getDocumentFileUrl, type AgentSource } from "../api";

function inline(value: string, sources: AgentSource[]): ReactNode[] {
  const pattern = /(\[FUENTE\s+\d+\]|\*\*[^*]+\*\*|__[^_]+__|`[^`]+`|\*[^*]+\*|_[^_]+_)/gi;
  return value.split(pattern).filter(Boolean).map((part, index) => {
    const sourceMatch = part.match(/^\[FUENTE\s+(\d+)\]$/i);
    if (sourceMatch) {
      const source = sources.find((item) => item.source_number === Number(sourceMatch[1]));
      return source ? <a key={index} className="uc-source-citation" href={getDocumentFileUrl(source.document_id)} target="_blank" rel="noreferrer">{source.document_title}{source.source_label ? ` · ${source.source_label}` : ""}</a> : <span key={index} className="uc-source-citation is-unavailable">Fuente {sourceMatch[1]}</span>;
    }
    if ((part.startsWith("**") && part.endsWith("**")) || (part.startsWith("__") && part.endsWith("__"))) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={index}>{part.slice(1, -1)}</code>;
    if ((part.startsWith("*") && part.endsWith("*")) || (part.startsWith("_") && part.endsWith("_"))) return <em key={index}>{part.slice(1, -1)}</em>;
    return <Fragment key={index}>{part}</Fragment>;
  });
}

function cells(line: string) { return line.trim().replace(/^\||\|$/g, "").split("|").map((item) => item.trim()); }
const tableDivider = (line: string) => /^\s*\|?\s*:?-{3,}/.test(line) && line.includes("|");
const blockStart = (line: string, next = "") => /^#{1,4}\s/.test(line) || /^```/.test(line) || /^\s*([-*_])\1{2,}\s*$/.test(line) || /^>/.test(line) || /^\s*([-*+]\s|\d+[.)]\s)/.test(line) || (line.includes("|") && tableDivider(next));

export default function AcademicMarkdown({ content, sources = [] }: { content: string; sources?: AgentSource[] }) {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) { index += 1; continue; }
    if (/^```/.test(line)) {
      const language = line.slice(3).trim(); const code: string[] = []; index += 1;
      while (index < lines.length && !/^```/.test(lines[index])) { code.push(lines[index]); index += 1; }
      index += 1; blocks.push(<pre key={blocks.length} data-language={language || undefined}><code>{code.join("\n")}</code></pre>); continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) { const children = inline(heading[2], sources); const key = blocks.length; blocks.push(heading[1].length === 1 ? <h1 key={key}>{children}</h1> : heading[1].length === 2 ? <h2 key={key}>{children}</h2> : <h3 key={key}>{children}</h3>); index += 1; continue; }
    if (/^\s*([-*_])\1{2,}\s*$/.test(line)) { blocks.push(<hr key={blocks.length} />); index += 1; continue; }
    if (line.startsWith(">")) { const quote: string[] = []; while (index < lines.length && lines[index].startsWith(">")) { quote.push(lines[index].replace(/^>\s?/, "")); index += 1; } blocks.push(<blockquote key={blocks.length}>{inline(quote.join(" "), sources)}</blockquote>); continue; }
    if (line.includes("|") && tableDivider(lines[index + 1] ?? "")) {
      const headers = cells(line); index += 2; const rows: string[][] = [];
      while (index < lines.length && lines[index].includes("|") && lines[index].trim()) { rows.push(cells(lines[index])); index += 1; }
      blocks.push(<table key={blocks.length}><thead><tr>{headers.map((item, cellIndex) => <th key={cellIndex}>{inline(item, sources)}</th>)}</tr></thead><tbody>{rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((item, cellIndex) => <td key={cellIndex}>{inline(item, sources)}</td>)}</tr>)}</tbody></table>); continue;
    }
    const unordered = line.match(/^\s*[-*+]\s+(.+)$/); const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (unordered || ordered) { const items: string[] = []; const orderedList = Boolean(ordered); const itemPattern = orderedList ? /^\s*\d+[.)]\s+(.+)$/ : /^\s*[-*+]\s+(.+)$/; while (index < lines.length) { const match = lines[index].match(itemPattern); if (!match) break; items.push(match[1]); index += 1; } const children = items.map((item, itemIndex) => <li key={itemIndex}>{inline(item, sources)}</li>); blocks.push(orderedList ? <ol key={blocks.length}>{children}</ol> : <ul key={blocks.length}>{children}</ul>); continue; }
    const paragraph = [line.trim()]; index += 1;
    while (index < lines.length && lines[index].trim() && !blockStart(lines[index], lines[index + 1] ?? "")) { paragraph.push(lines[index].trim()); index += 1; }
    blocks.push(<p key={blocks.length}>{paragraph.map((item, paragraphIndex) => <Fragment key={paragraphIndex}>{paragraphIndex > 0 && <br />}{inline(item, sources)}</Fragment>)}</p>);
  }
  return <div className="uc-academic-markdown">{blocks}</div>;
}
