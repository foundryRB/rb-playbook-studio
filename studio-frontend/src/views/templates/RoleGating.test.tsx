import { intent } from '@psa-department-of-engineering/vitest-intent';
import { render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, vi } from 'vitest';

vi.mock('@/utils', async (importOriginal) => {
    const actual = await importOriginal<typeof import('@/utils')>();
    return { ...actual, apiFetch: vi.fn() };
});

import type { AgentResponse, DoorResponse, StandingResponse } from '@/models';
import { apiFetch } from '@/utils';
import { useAgentDetail } from '@/viewmodels/agentdetail';
import { useDoorDetail } from '@/viewmodels/doordetail';
import { useIdentity } from '@/viewmodels/identity';
import { useNav } from '@/viewmodels/nav';
import { useSync } from '@/viewmodels/sync';
import { SyncControls } from '@/views/molecules/SyncControls';
import { AgentReader } from '@/views/organisms/AgentReader';
import { CreateSkillForm } from '@/views/organisms/CreateSkillForm';
import { DoorReader } from '@/views/organisms/DoorReader';
import { GovernanceRail } from '@/views/organisms/GovernanceRail';
import { SidebarNav } from '@/views/organisms/SidebarNav';

const standing = (overrides: Partial<StandingResponse>): StandingResponse => ({
    name: 'someone',
    email: 'someone@example.com',
    service: false,
    role: 'reader',
    galaxies: [],
    atoms: [],
    can_edit_playbook: false,
    can_administer: false,
    can_validate: false,
    tokens: true,
    ...overrides,
});

const READER = standing({});
const WRITER = standing({
    role: 'galaxy writer',
    galaxies: ['craft'],
    can_validate: true,
});

const agent = (canEdit: boolean): AgentResponse => ({
    name: 'alpha-agent',
    title: 'The alpha agent',
    description: 'Runs alpha.',
    galaxy: 'craft',
    refs: ['REF-Alpha'],
    skills: ['do-alpha'],
    doors: [],
    posture: { permission: 'auto', writes: true, fresh_eyes: false },
    appearance: null,
    summary: 'Runs alpha.',
    raw: '---\nname: alpha-agent\n---\n\nBody.\n',
    body: 'Body.',
    can_edit: canEdit,
});

const door = (canEdit: boolean): DoorResponse => ({
    name: 'alpha-door',
    kind: 'mcp',
    galaxy: 'craft',
    refs: ['REF-Alpha'],
    summary: 'Knock here.',
    raw: '---\nname: alpha-door\n---\n\n# MCP: alpha-door\n',
    can_edit: canEdit,
});

const graph = {
    nodes: [
        { id: 'REF-Alpha', kind: 'ref', domain: 'practice', galaxy: 'craft' },
        { id: 'REF-Maker', kind: 'ref', domain: 'practice', galaxy: 'maker' },
    ],
    edges: [],
};

const sign = (me: StandingResponse | null) => useIdentity.setState({ me, loaded: true });

describe('role gating', () => {
    beforeEach(() => {
        vi.mocked(apiFetch).mockReset();
        vi.mocked(apiFetch).mockImplementation(async (path: string) => {
            if (path === '/api/agents/alpha-agent') return agent(false);
            if (path === '/api/claims') return [];
            if (path === '/api/playbook') return { title: 'AI Playbook', sections: [], raw: '' };
            if (path === '/api/graph') return graph;
            throw new Error(`unexpected ${path}`);
        });
        useNav.setState({ view: 'map', expanded: {} });
        useSync.setState({
            enabled: true,
            status: { unpushed_commits: 2, diff_stat: '', repo: 'acme/playbook' },
            busy: null,
            error: null,
        });
    });

    intent('INT-AUTH-012', "a reader's UI shows no write control", async () => {
        sign(READER);
        useDoorDetail.setState({ door: door(false), loading: false, error: null, editing: false });
        useAgentDetail.setState({ selectedAgent: 'alpha-agent', agent: null });

        const doorView = render(<DoorReader />);
        expect(within(doorView.container).queryByText('Edit')).toBeNull();
        doorView.unmount();

        const agentView = render(<AgentReader />);
        await waitFor(() => expect(screen.getByText('alpha-agent')).toBeInTheDocument());
        expect(within(agentView.container).queryByText('Edit')).toBeNull();
        agentView.unmount();

        const sync = render(<SyncControls />);
        expect(within(sync.container).getByText('2 unpushed')).toBeInTheDocument();
        expect(within(sync.container).queryByText('Push')).toBeNull();
        expect(within(sync.container).queryByText('Refresh')).toBeNull();
        sync.unmount();

        const rail = render(<GovernanceRail />);
        expect(within(rail.container).queryByText('Run validation')).toBeNull();
        rail.unmount();

        const nav = render(<SidebarNav />);
        expect(within(nav.container).queryByText('+ REF')).toBeNull();
        expect(within(nav.container).queryByText('+ Card')).toBeNull();
        nav.unmount();
    });

    intent('INT-AUTH-012', 'a write control renders where the document says can_edit', () => {
        sign(WRITER);
        useDoorDetail.setState({ door: door(true), loading: false, error: null, editing: false });
        render(<DoorReader />);
        expect(screen.getByText('Edit')).toBeInTheDocument();
    });

    intent('INT-AUTH-012', "a galaxy writer's UI offers create only in its galaxy", async () => {
        sign(WRITER);
        const nav = render(<SidebarNav />);
        for (const label of ['+ REF', '+ Skill', '+ Agent', '+ Card']) {
            expect(within(nav.container).getByText(label)).toBeInTheDocument();
        }
        nav.unmount();

        const form = render(<CreateSkillForm />);
        const select = within(form.container).getByRole('combobox');
        const options = within(select)
            .getAllByRole('option')
            .map((o) => o.textContent);
        expect(options).toEqual(['craft']);

        const rail = render(<GovernanceRail />);
        expect(within(rail.container).getByText('Run validation')).toBeInTheDocument();
        await waitFor(() => expect(apiFetch).toHaveBeenCalledWith('/api/claims'));
    });

    intent('INT-AUTH-012', 'nobody signed in sees no write control either', () => {
        sign(null);
        const nav = render(<SidebarNav />);
        expect(within(nav.container).queryByText('+ REF')).toBeNull();
        nav.unmount();
        const sync = render(<SyncControls />);
        expect(within(sync.container).queryByText('Push')).toBeNull();
    });
});
