import { useEffect } from 'react';

import { useIdentity } from '@/viewmodels/identity';

const FIELD_CLASSES =
    'w-full rounded-md border border-input bg-background/70 px-3 py-1.5 text-sm outline-none placeholder:text-muted-foreground/50 focus:ring-1 focus:ring-ring';

const NO_GALAXIES: string[] = [];

export interface GalaxyFieldProps {
    label: string;
    value: string;
    onChange: (galaxy: string) => void;
}

/** The galaxy a new planet joins: only the galaxies the signed-in person may
 *  create in, as /api/me names them. */
export const GalaxyField = ({ label, value, onChange }: GalaxyFieldProps) => {
    const galaxies = useIdentity((state) => state.me?.galaxies ?? NO_GALAXIES);

    useEffect(() => {
        if (galaxies.length > 0 && !galaxies.includes(value)) {
            onChange(galaxies[0]);
        }
    }, [galaxies, value, onChange]);

    return (
        <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
            {label}
            <select
                className={FIELD_CLASSES}
                value={value}
                onChange={(e) => onChange(e.target.value)}
            >
                {galaxies.map((g) => (
                    <option key={g} value={g}>
                        {g}
                    </option>
                ))}
            </select>
        </label>
    );
};

export interface OwnersFieldProps {
    value: string;
    onChange: (owners: string) => void;
}

/** Who will own the new atom: their emails become its line in OWNERS. */
export const OwnersField = ({ value, onChange }: OwnersFieldProps) => (
    <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
        Owners (emails, optional: they may edit it once it exists)
        <input
            className={FIELD_CLASSES}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="ana@example.com bruno@example.com"
        />
    </label>
);
