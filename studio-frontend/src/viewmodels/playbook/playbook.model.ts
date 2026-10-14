import type { PlaybookResponse, PlaybookSectionResponse } from '@/models';

/** The governance section every session must check; pinned first in the UI. */
export const selectViolationsSection = (
    doc: PlaybookResponse | null,
): PlaybookSectionResponse | null =>
    doc?.sections.find((s) => s.title.toLowerCase().startsWith('top violations')) ?? null;

export const selectOtherSections = (doc: PlaybookResponse | null): PlaybookSectionResponse[] =>
    doc?.sections.filter((s) => !s.title.toLowerCase().startsWith('top violations')) ?? [];

/** Task-routing rows (task column) whose REF column mentions the given REF. */
export function selectRoutingRowsFor(doc: PlaybookResponse | null, refName: string): string[] {
    const routing = doc?.sections.find((s) => s.title.toLowerCase().startsWith('task routing'));
    if (!routing) {
        return [];
    }
    return routing.body
        .split('\n')
        .filter((line) => line.startsWith('|') && line.includes(refName))
        .map((line) => line.split('|')[1]?.trim() ?? '')
        .filter((task) => task.length > 0 && !/^-+$/.test(task));
}

export interface ViolationItem {
    number: number;
    title: string;
    body: string;
}

export interface ParsedViolations {
    intro: string;
    items: ViolationItem[];
    footer: string;
}

/** Split the violations section into scannable items: bold lead = the rule. */
export function parseViolations(body: string): ParsedViolations {
    const firstItem = body.search(/^\d+\.\s/m);
    if (firstItem === -1) {
        return { intro: body, items: [], footer: '' };
    }
    const intro = body.slice(0, firstItem).trim();
    const rest = body.slice(firstItem);
    const chunks = rest.split(/\n(?=\d+\.\s)/);
    const items: ViolationItem[] = [];
    let footer = '';
    chunks.forEach((chunk, i) => {
        let text = chunk;
        if (i === chunks.length - 1) {
            const paragraphs = text.split(/\n\n+/);
            text = paragraphs[0];
            footer = paragraphs.slice(1).join('\n\n').trim();
        }
        const number = Number.parseInt(text, 10);
        const title = /\*\*(.+?)\*\*/.exec(text)?.[1] ?? text.slice(0, 60);
        items.push({ number, title, body: text.trim() });
    });
    return { intro, items, footer };
}
