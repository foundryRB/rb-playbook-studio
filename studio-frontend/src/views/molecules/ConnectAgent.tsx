import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import type { PersonalTokenResponse } from '@/models';
import { apiFetch } from '@/utils';
import { useIdentity } from '@/viewmodels/identity';

export interface ConnectAgentProps {
    /** When set, the panel adds the ask that installs the toolchain carrying this skill. */
    skillName?: string;
}

/**
 * The deployed studio has no local skills runtime: effects on your machine
 * happen through your own agent (the client-executes idiom, ADR-004).
 * Offers the copyable connect one-liner and, per skill, the ask that installs it:
 * the whole toolchain through get_install_command, which writes only what differs.
 *
 * A signed-in person connects with their own personal token, minted here and
 * shown once: the agent then acts as them, with their rights, and every change
 * it makes carries their name. The stand-alone studio's Basic gate makes its
 * holder the service, whose shared credential the one-liner carries instead,
 * fetched from /api/agent-credential when the panel mounts.
 */
export const ConnectAgent = ({ skillName }: ConnectAgentProps) => {
    const me = useIdentity((state) => state.me);
    const service = me?.service ?? false;
    const [copied, setCopied] = useState<string | null>(null);
    const [credential, setCredential] = useState<string | null>(null);
    const [token, setToken] = useState<PersonalTokenResponse | null>(null);
    const [failed, setFailed] = useState<string | null>(null);
    const [minting, setMinting] = useState(false);

    useEffect(() => {
        if (!service) return;
        let cancelled = false;
        apiFetch<{ credential: string }>('/api/agent-credential')
            .then((r) => {
                if (!cancelled) setCredential(r.credential);
            })
            .catch(() => {
                if (!cancelled) setFailed('credential');
            });
        return () => {
            cancelled = true;
        };
    }, [service]);

    const mint = async () => {
        setMinting(true);
        setFailed(null);
        try {
            setToken(await apiFetch<PersonalTokenResponse>('/api/tokens', { method: 'POST' }));
        } catch (err) {
            setFailed(err instanceof Error ? err.message : 'token');
        } finally {
            setMinting(false);
        }
    };

    const header = service
        ? `Authorization: Basic ${credential ?? '<credentials>'}`
        : `Authorization: Bearer ${token?.token ?? '<your-token>'}`;
    const oneLiner = `claude mcp add --scope user --transport http playbook ${window.location.origin}/mcp --header "${header}"`;
    const ask = skillName
        ? `Install the playbook toolchain (it carries ${skillName}): call get_install_command for this harness and run the line it returns.`
        : null;

    const copy = (label: string, text: string) => {
        void navigator.clipboard.writeText(text).then(() => {
            setCopied(label);
            window.setTimeout(() => setCopied(null), 2000);
        });
    };

    return (
        <div className="flex flex-col gap-2">
            <p className="text-xs text-muted-foreground">
                {skillName
                    ? 'Skills install on your machine, through your agent. Connect it once:'
                    : 'Connect your agent once; it gets every studio tool, acting as you (reads, gated edits within your rights, skill installs):'}
            </p>
            {!service && !token && (
                <Button
                    className="h-7 w-full px-2 text-xs"
                    disabled={minting || !me?.tokens}
                    onClick={() => void mint()}
                >
                    {minting ? 'Minting...' : 'Mint my token'}
                </Button>
            )}
            <pre className="overflow-x-auto whitespace-pre rounded-md border border-border bg-background/80 p-2 font-mono text-[10px] leading-relaxed text-muted-foreground">
                {oneLiner}
            </pre>
            <Button
                variant="outline"
                className="h-6 w-full px-2 text-xs"
                disabled={!service && !token}
                onClick={() => copy('command', oneLiner)}
            >
                {copied === 'command' ? 'Copied' : 'Copy connect command'}
            </Button>
            {ask && (
                <>
                    <p className="text-xs text-muted-foreground">then ask your agent:</p>
                    <pre className="overflow-x-auto whitespace-pre-wrap rounded-md border border-border bg-background/80 p-2 font-mono text-[10px] leading-relaxed text-muted-foreground">
                        {ask}
                    </pre>
                    <Button
                        variant="outline"
                        className="h-6 w-full px-2 text-xs"
                        onClick={() => copy('ask', ask)}
                    >
                        {copied === 'ask' ? 'Copied' : 'Copy the ask'}
                    </Button>
                </>
            )}
            <p className="text-[10px] text-muted-foreground/70">
                {service
                    ? failed
                        ? "Credential unavailable right now; replace <credentials> with this site's base64 HTTP Basic pair (user:password)."
                        : 'The command carries this site’s shared HTTP Basic credential (the service’s), already filled in.'
                    : !me?.tokens
                      ? 'This studio mints no personal tokens yet; ask its admin.'
                      : failed
                        ? `No token minted: ${failed}`
                        : token
                          ? `Your token, shown once: it acts as ${token.email} until ${token.expires_at}. Mint another whenever you need one.`
                          : 'Your token names you and expires; an admin can revoke the tokens issued to you.'}
            </p>
        </div>
    );
};
