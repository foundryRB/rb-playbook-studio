import { intent } from '@psa-department-of-engineering/vitest-intent';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';

import { useGalaxyDetail } from '@/viewmodels/galaxydetail';
import { useNav } from '@/viewmodels/nav';
import { corpusLinkComponents, resolveCorpusHref } from '@/views/molecules/CorpusLink';
import { Markdown } from '@/views/molecules/Markdown';

describe('resolveCorpusHref', () => {
    it('resolves a galaxy routing doc', () => {
        expect(resolveCorpusHref('galaxies/craft/GALAXY.md')).toEqual({
            kind: 'galaxy',
            id: 'craft',
        });
    });

    it('resolves a REF, and a skill without the REF pattern swallowing it', () => {
        expect(resolveCorpusHref('galaxies/craft/REF-Foundry.md')).toEqual({
            kind: 'ref',
            id: 'REF-Foundry',
        });
        expect(resolveCorpusHref('galaxies/craft/skills/bootstrap-starlight/SKILL.md')).toEqual({
            kind: 'skill',
            id: 'bootstrap-starlight',
        });
    });

    it('resolves an agent to its reader', () => {
        expect(resolveCorpusHref('galaxies/craft/agents/ticket-resolver.md')).toEqual({
            kind: 'agent',
            id: 'ticket-resolver',
        });
    });

    it('tolerates the leading-./ and anchor forms an author may write', () => {
        expect(resolveCorpusHref('./galaxies/maker/GALAXY.md')).toEqual({
            kind: 'galaxy',
            id: 'maker',
        });
        expect(resolveCorpusHref('galaxies/games/GALAXY.md#task-routing')).toEqual({
            kind: 'galaxy',
            id: 'games',
        });
    });

    it('returns null for what the studio cannot open', () => {
        expect(resolveCorpusHref('https://example.com/x')).toBeNull();
        expect(resolveCorpusHref('../archive/old-note.md')).toBeNull();
        expect(resolveCorpusHref('')).toBeNull();
    });
});

describe('corpusLinkComponents', () => {
    beforeEach(() => {
        useNav.setState({ view: 'playbook' });
        useGalaxyDetail.setState({ selectedGalaxy: null });
    });

    intent(
        'INT-NAV-001',
        'a corpus link opens its target in the studio instead of navigating away',
        () => {
            render(
                <Markdown components={corpusLinkComponents}>
                    {'See [craft](galaxies/craft/GALAXY.md).'}
                </Markdown>,
            );

            // Rendered as a control, not an anchor: an <a href> would take the
            // browser out of the SPA, which is the defect being fixed.
            const link = screen.getByRole('button', { name: 'craft' });
            expect(link.tagName).toBe('BUTTON');

            fireEvent.click(link);

            expect(useGalaxyDetail.getState().selectedGalaxy).toBe('craft');
            expect(useNav.getState().view).toBe('galaxy');
        },
    );

    intent('INT-NAV-001', 'a path the studio cannot open renders inert, not as a link', () => {
        render(
            <Markdown components={corpusLinkComponents}>
                {'See [old](../archive/old-note.md).'}
            </Markdown>,
        );

        expect(screen.queryByRole('link', { name: 'old' })).toBeNull();
        expect(screen.queryByRole('button', { name: 'old' })).toBeNull();
        expect(screen.getByText('old')).toBeTruthy();
    });

    it('keeps an external URL a real anchor, opening in a new tab', () => {
        render(
            <Markdown components={corpusLinkComponents}>
                {'See [outside](https://example.com/x).'}
            </Markdown>,
        );

        const anchor = screen.getByRole('link', { name: 'outside' });
        expect(anchor.getAttribute('href')).toBe('https://example.com/x');
        expect(anchor.getAttribute('target')).toBe('_blank');
    });
});
