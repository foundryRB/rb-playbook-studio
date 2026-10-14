import { describe, expect, it } from 'vitest';

import { layoutDocument, normalizeToken } from './panel.model';

const resolve = (token: string): string | null =>
    ['REF-Domain', 'bootstrap-ref', 'playbook'].includes(token) ? token : null;

describe('panel.model layoutDocument', () => {
    it('classifies headings, bullets, quotes, and code fences', () => {
        const lines = layoutDocument(
            '---\nname: x\n---\n# Title\n\n## Section\n\n> purpose line\n\n- item one\n\n```\ncode line\n```\n',
            resolve,
        );
        const styles = lines.map((l) => l.style);
        expect(styles).toContain('h1');
        expect(styles).toContain('h2');
        expect(styles).toContain('quote');
        expect(styles).toContain('bullet');
        expect(styles).toContain('code');
        expect(lines.find((l) => l.style === 'code')?.text).toBe('code line');
    });

    it('resolves backticked and bare tokens into link ranges on the display text', () => {
        const lines = layoutDocument('Read `REF-Domain.md` before REF-Domain work.', resolve);
        const line = lines[0];
        expect(line.text).toBe('Read REF-Domain.md before REF-Domain work.');
        expect(line.links).toHaveLength(2);
        const [a, b] = line.links;
        expect(line.text.slice(a.start, a.end)).toBe('REF-Domain.md');
        expect(a.target).toBe('REF-Domain');
        expect(line.text.slice(b.start, b.end)).toBe('REF-Domain');
        expect(b.target).toBe('REF-Domain');
    });

    it('keeps link ranges valid across wrapped lines', () => {
        const long = `${'word '.repeat(20)}[the door](playbook.md) ${'tail '.repeat(20)}`;
        const lines = layoutDocument(long, resolve);
        const linked = lines.filter((l) => l.links.length > 0);
        expect(linked.length).toBeGreaterThan(0);
        for (const line of linked) {
            for (const link of line.links) {
                expect(link.start).toBeGreaterThanOrEqual(0);
                expect(link.end).toBeLessThanOrEqual(line.text.length);
                expect(link.target).toBe('playbook');
            }
        }
        const joined = linked
            .flatMap((l) => l.links.map((k) => l.text.slice(k.start, k.end)))
            .join('');
        expect(joined.replace(/\s/g, '')).toBe('thedoor');
    });

    it('normalizes path and extension tokens', () => {
        expect(normalizeToken('galaxies/craft/REF-Domain.md')).toBe('REF-Domain');
        expect(normalizeToken('./playbook.md')).toBe('playbook');
    });

    it('flattens table rows and drops separators', () => {
        const lines = layoutDocument(
            '| Layer | Holds |\n|---|---|\n| Domain | `REF-Domain.md` |',
            resolve,
        );
        expect(lines).toHaveLength(2);
        expect(lines[0].text).toBe('Layer  ·  Holds');
        expect(lines[1].text).toBe('Domain  ·  REF-Domain.md');
        expect(lines[1].links[0]?.target).toBe('REF-Domain');
    });
});
