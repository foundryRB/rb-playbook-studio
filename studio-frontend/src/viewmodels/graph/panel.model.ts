/** Layout engine for the in-headset reading panel: markdown to styled,
 *  wrapped lines with link ranges that survive wrapping, so a controller ray
 *  can hit a cross-reference and travel there. Pure and unit-testable; the
 *  desktop panel renders real DOM instead and never touches this. */

export type LineStyle = 'h1' | 'h2' | 'h3' | 'body' | 'bullet' | 'quote' | 'code' | 'gap';

export interface DocLink {
    /** Character range inside the line's final display text. */
    start: number;
    end: number;
    /** A universe body id (REF-X, skill, door) the link travels to. */
    target: string;
}

export interface DocLine {
    text: string;
    style: LineStyle;
    indent: number;
    links: DocLink[];
}

const WRAP: Record<LineStyle, number> = {
    h1: 30,
    h2: 38,
    h3: 44,
    body: 58,
    bullet: 54,
    quote: 54,
    code: 62,
    gap: 999,
};

interface Segment {
    text: string;
    target: string | null;
}

/** Normalize a link token to a body id candidate: strip paths and .md. */
export function normalizeToken(token: string): string {
    const clean = token.trim().replace(/^\.\//, '');
    const last = clean.split('/').pop() ?? clean;
    return last.replace(/\.md$/i, '');
}

/** Inline markdown to display segments: links, code, bold, bare REF tokens. */
function transformInline(raw: string, resolve: (token: string) => string | null): Segment[] {
    const pattern =
        /\[([^\]]+)\]\(([^)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*|\bREF-[A-Za-z0-9][A-Za-z0-9-]*\b/g;
    const segments: Segment[] = [];
    let cursor = 0;
    for (const match of raw.matchAll(pattern)) {
        const index = match.index ?? 0;
        if (index > cursor) {
            segments.push({ text: raw.slice(cursor, index), target: null });
        }
        if (match[1] !== undefined) {
            segments.push({ text: match[1], target: resolve(normalizeToken(match[2])) });
        } else if (match[3] !== undefined) {
            segments.push({ text: match[3], target: resolve(normalizeToken(match[3])) });
        } else if (match[4] !== undefined) {
            segments.push({ text: match[4], target: null });
        } else {
            segments.push({ text: match[0], target: resolve(match[0]) });
        }
        cursor = index + match[0].length;
    }
    if (cursor < raw.length) {
        segments.push({ text: raw.slice(cursor), target: null });
    }
    return segments;
}

/** Word-wrap segments into lines of at most `cols`, remapping link ranges. */
function wrapSegments(segments: Segment[], style: LineStyle, indent: number): DocLine[] {
    const full = segments.map((s) => s.text).join('');
    const links: DocLink[] = [];
    let offset = 0;
    for (const segment of segments) {
        if (segment.target) {
            links.push({
                start: offset,
                end: offset + segment.text.length,
                target: segment.target,
            });
        }
        offset += segment.text.length;
    }

    const cols = WRAP[style];
    const lines: DocLine[] = [];
    let lineStart = 0;
    while (lineStart < full.length || lines.length === 0) {
        let lineEnd = Math.min(lineStart + cols, full.length);
        if (lineEnd < full.length) {
            const space = full.lastIndexOf(' ', lineEnd);
            if (space > lineStart + Math.floor(cols / 3)) {
                lineEnd = space;
            }
        }
        const text = full.slice(lineStart, lineEnd);
        const localLinks = links
            .filter((l) => l.end > lineStart && l.start < lineEnd)
            .map((l) => ({
                start: Math.max(l.start - lineStart, 0),
                end: Math.min(l.end - lineStart, text.length),
                target: l.target,
            }));
        lines.push({ text, style, indent, links: localLinks });
        lineStart = lineEnd + (full[lineEnd] === ' ' ? 1 : 0);
        if (lineEnd >= full.length) {
            break;
        }
    }
    return lines;
}

/** Parse a whole document into display lines for the in-scene panel. */
export function layoutDocument(
    markdown: string,
    resolve: (token: string) => string | null,
): DocLine[] {
    const body = markdown.replace(/^---[\s\S]*?---\n/, '');
    const out: DocLine[] = [];
    let inFence = false;
    for (const raw of body.split('\n')) {
        if (/^\s*```/.test(raw)) {
            inFence = !inFence;
            continue;
        }
        if (inFence) {
            out.push(
                ...wrapSegments([{ text: raw.replace(/\t/g, '    '), target: null }], 'code', 0),
            );
            continue;
        }
        const trimmed = raw.trimEnd();
        if (trimmed === '') {
            if (out.length > 0 && out[out.length - 1].style !== 'gap') {
                out.push({ text: '', style: 'gap', indent: 0, links: [] });
            }
            continue;
        }
        if (/^\s*---+\s*$/.test(trimmed)) {
            continue;
        }
        const heading = /^(#{1,6})\s+(.*)$/.exec(trimmed);
        if (heading) {
            const style: LineStyle =
                heading[1].length === 1 ? 'h1' : heading[1].length === 2 ? 'h2' : 'h3';
            out.push(...wrapSegments(transformInline(heading[2], resolve), style, 0));
            continue;
        }
        const bullet = /^(\s*)[-*]\s+(.*)$/.exec(trimmed);
        if (bullet) {
            out.push(
                ...wrapSegments(
                    transformInline(bullet[2], resolve),
                    'bullet',
                    bullet[1].length > 0 ? 1 : 0,
                ),
            );
            continue;
        }
        const quote = /^>\s?(.*)$/.exec(trimmed);
        if (quote) {
            out.push(...wrapSegments(transformInline(quote[1], resolve), 'quote', 0));
            continue;
        }
        if (/^\s*\|/.test(trimmed)) {
            // Tables flatten to dot-joined rows; separator rows vanish.
            if (/^\s*\|[\s:|-]+\|?\s*$/.test(trimmed)) {
                continue;
            }
            const cells = trimmed
                .split('|')
                .map((c) => c.trim())
                .filter((c) => c.length > 0);
            out.push(...wrapSegments(transformInline(cells.join('  ·  '), resolve), 'body', 1));
            continue;
        }
        out.push(...wrapSegments(transformInline(trimmed, resolve), 'body', 0));
    }
    while (out.length > 0 && out[out.length - 1].style === 'gap') {
        out.pop();
    }
    return out;
}
