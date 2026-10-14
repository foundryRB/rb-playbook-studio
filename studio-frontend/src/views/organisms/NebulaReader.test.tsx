import { beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import type { NebulaDetailResponse } from '@/models';
import { useNebulae } from '@/viewmodels/nebulae';
import { NebulaReader } from '@/views/organisms/NebulaReader';

const detail: NebulaDetailResponse = {
    territory: 'test-territory',
    subject: 'a reader fixture',
    raw:
        '# Nebula: test-territory\n\n' +
        'See [alpha-note](alpha-note.md), [gone](gone.md), and [outside](https://example.com/x).\n',
    notes: [
        {
            name: 'alpha-note',
            type: 'tool',
            confidence: 'high',
            vote: '3-0',
            seats: ['operator'],
            sources: ['https://example.com/src'],
            links: [],
            status: 'unsmelted',
            body: 'Alpha body text.',
        },
    ],
};

describe('NebulaReader', () => {
    beforeEach(() => {
        useNebulae.setState({
            detail,
            detailLoading: false,
            detailError: null,
            selectedNebula: 'test-territory',
        });
    });

    it('opens a roster link in place instead of navigating the SPA away', () => {
        render(<NebulaReader />);
        expect(screen.queryByText('Alpha body text.')).not.toBeInTheDocument();
        fireEvent.click(screen.getByTitle('Open the alpha-note note'));
        expect(screen.getByText('Alpha body text.')).toBeInTheDocument();
    });

    it('renders unresolvable links inert and external links as real anchors', () => {
        render(<NebulaReader />);
        const gone = screen.getByText('gone');
        expect(gone.tagName).toBe('SPAN');
        expect(gone.closest('a')).toBeNull();
        const outside = screen.getByText('outside').closest('a');
        expect(outside).not.toBeNull();
        expect(outside!.getAttribute('target')).toBe('_blank');
    });
});
