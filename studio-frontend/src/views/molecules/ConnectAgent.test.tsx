import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('@/utils', async (importOriginal) => {
    const actual = await importOriginal<typeof import('@/utils')>();
    return { ...actual, apiFetch: vi.fn() };
});

import type { StandingResponse } from '@/models';
import { apiFetch } from '@/utils';
import { useIdentity } from '@/viewmodels/identity';
import { ConnectAgent } from '@/views/molecules/ConnectAgent';
import { IdentityChip } from '@/views/molecules/IdentityChip';

// base64('demo:pass')
const CRED = 'ZGVtbzpwYXNz';
const TOKEN = 'pst1.payload.signature';

const me = (overrides: Partial<StandingResponse>): StandingResponse => ({
    name: 'ana',
    email: 'ana@example.com',
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

describe('ConnectAgent for a signed-in person', () => {
    beforeEach(() => {
        vi.mocked(apiFetch).mockReset();
        vi.mocked(apiFetch).mockResolvedValue({
            token: TOKEN,
            email: 'ana@example.com',
            name: 'ana',
            expires_at: '2027-01-07T00:00:00Z',
        });
        useIdentity.setState({ me: me({}), loaded: true });
    });

    it('mints their own token and fills it in as a Bearer header', async () => {
        render(<ConnectAgent />);
        expect(screen.getByText(/claude mcp add/).textContent).toContain(
            'Authorization: Bearer <your-token>',
        );
        fireEvent.click(screen.getByText('Mint my token'));
        await waitFor(() => {
            expect(screen.getByText(/claude mcp add/).textContent).toContain(
                `Authorization: Bearer ${TOKEN}`,
            );
        });
        expect(apiFetch).toHaveBeenCalledWith('/api/tokens', { method: 'POST' });
        expect(apiFetch).not.toHaveBeenCalledWith('/api/agent-credential');
        expect(screen.getByText(/acts as ana@example.com/)).toBeInTheDocument();
    });

    it('says so when the studio mints no tokens', () => {
        useIdentity.setState({ me: me({ tokens: false }), loaded: true });
        render(<ConnectAgent />);
        expect(screen.getByText('Mint my token')).toBeDisabled();
        expect(screen.getByText(/mints no personal tokens/)).toBeInTheDocument();
    });

    it('asks the agent for the whole toolchain through get_install_command', () => {
        render(<ConnectAgent skillName="digest" />);
        const ask = screen.getByText(/get_install_command/);
        expect(ask.textContent).toContain('digest');
        expect(ask.textContent).not.toContain('install-skill');
    });
});

describe('ConnectAgent for the service', () => {
    beforeEach(() => {
        vi.mocked(apiFetch).mockReset();
        vi.mocked(apiFetch).mockResolvedValue({ credential: CRED });
        useIdentity.setState({
            me: me({ service: true, role: 'admin', tokens: false }),
            loaded: true,
        });
    });

    it('fills the shared credential into the one-liner on mount', async () => {
        render(<ConnectAgent />);
        await waitFor(() => {
            expect(screen.getByText(/claude mcp add/).textContent).toContain(
                `Authorization: Basic ${CRED}`,
            );
        });
        expect(apiFetch).toHaveBeenCalledWith('/api/agent-credential');
        expect(screen.queryByText('Mint my token')).toBeNull();
    });

    it('falls back to the placeholder when the credential is unavailable', async () => {
        vi.mocked(apiFetch).mockRejectedValue(new Error('503'));
        render(<ConnectAgent />);
        await waitFor(() => {
            expect(screen.getByText(/Credential unavailable/)).toBeInTheDocument();
        });
        expect(screen.getByText(/claude mcp add/).textContent).toContain('<credentials>');
    });
});

describe('IdentityChip', () => {
    it('shows who you are and your role', () => {
        useIdentity.setState({
            me: me({ role: 'galaxy writer', galaxies: ['craft'] }),
            loaded: true,
        });
        render(<IdentityChip />);
        expect(screen.getByText('ana')).toBeInTheDocument();
        expect(screen.getByText('galaxy writer')).toBeInTheDocument();
    });

    it('says when nobody is signed in', () => {
        useIdentity.setState({ me: null, loaded: true });
        render(<IdentityChip />);
        expect(screen.getByText('not signed in')).toBeInTheDocument();
    });
});
