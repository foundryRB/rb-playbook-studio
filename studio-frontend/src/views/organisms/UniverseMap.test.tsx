import { beforeEach, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import type { GraphResponse } from '@/models';
import { useGraph } from '@/viewmodels/graph';
import { useNebulae } from '@/viewmodels/nebulae';
import { UniverseMap } from '@/views/organisms/UniverseMap';

const graph: GraphResponse = { nodes: [], edges: [] };

describe('UniverseMap nebula roster errors', () => {
    beforeEach(() => {
        useGraph.setState({ graph, loading: false, error: null, load: async () => {} });
        useNebulae.setState({
            nebulae: [],
            error: null,
            loading: false,
            load: async () => {},
        });
    });

    it('shows a muted indicator when the roster is unavailable', () => {
        useNebulae.setState({ error: 'roster fetch failed' });
        render(<UniverseMap />);
        expect(screen.getByText('nebulae unavailable')).toBeInTheDocument();
    });

    it('omits the indicator when the roster loads', () => {
        render(<UniverseMap />);
        expect(screen.queryByText('nebulae unavailable')).not.toBeInTheDocument();
    });
});
