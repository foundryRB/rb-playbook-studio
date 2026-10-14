import { useEffect } from 'react';

import { useIdentity } from '@/viewmodels/identity';

/** Who you are on this studio, and your role. Renders nothing until the studio
 *  answers, and says so plainly when nobody is signed in. */
export const IdentityChip = () => {
    const me = useIdentity((state) => state.me);
    const loaded = useIdentity((state) => state.loaded);
    const load = useIdentity((state) => state.load);

    useEffect(() => {
        void load();
    }, [load]);

    if (!loaded) return null;
    if (!me) {
        return (
            <span className="rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground">
                not signed in
            </span>
        );
    }

    const owned = [
        me.galaxies.length > 0 ? `writes in: ${me.galaxies.join(', ')}` : null,
        me.atoms.length > 0 ? `owns: ${me.atoms.join(', ')}` : null,
    ].filter(Boolean);

    return (
        <span
            title={[me.email, ...owned].join('\n')}
            className="flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs"
        >
            <span className="max-w-40 truncate font-medium text-foreground">{me.name}</span>
            <span className="text-muted-foreground">{me.role}</span>
        </span>
    );
};
