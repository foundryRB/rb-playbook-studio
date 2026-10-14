import { useCallback } from 'react';

import { Button } from '@/components/ui/button';
import { DOMAIN_ORDER, useGraph } from '@/viewmodels/graph';
import { useCreateRef } from '@/viewmodels/createref';
import { useNav } from '@/viewmodels/nav';
import { GalaxyField } from '@/views/molecules/CreateFields';
import { ValidationBanner } from '@/views/molecules/ValidationBanner';

const FIELD_CLASSES =
    'w-full rounded-md border border-input bg-background/70 px-3 py-1.5 text-sm outline-none placeholder:text-muted-foreground/50 focus:ring-1 focus:ring-ring';

export const CreateRefForm = () => {
    const name = useCreateRef((state) => state.name);
    const domain = useCreateRef((state) => state.domain);
    const galaxy = useCreateRef((state) => state.galaxy);
    const title = useCreateRef((state) => state.title);
    const summary = useCreateRef((state) => state.summary);
    const submitting = useCreateRef((state) => state.submitting);
    const error = useCreateRef((state) => state.error);
    const report = useCreateRef((state) => state.report);
    const setField = useCreateRef((state) => state.setField);
    const reset = useCreateRef((state) => state.reset);
    const submit = useCreateRef((state) => state.submit);
    const setGalaxy = useCallback((value: string) => setField('galaxy', value), [setField]);

    const load = useGraph((state) => state.load);
    const select = useGraph((state) => state.select);
    const setView = useNav((state) => state.setView);

    const onSubmit = async () => {
        const created = await submit();
        if (created) {
            reset();
            await load();
            select(created.name);
            setView('ref');
        }
    };

    return (
        <div className="mx-auto flex max-w-xl flex-col gap-4">
            <div>
                <h2 className="text-lg font-bold tracking-tight">New REF</h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                    Creates a template-conformant REF (frontmatter, title, summary, §1) and runs the
                    intent gates; the file is removed again if they fail. Add it to the playbook
                    routing table afterwards so tasks load it.
                </p>
            </div>

            <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
                Name (REF-PascalCase)
                <input
                    className={`${FIELD_CLASSES} font-mono`}
                    value={name}
                    onChange={(e) => setField('name', e.target.value)}
                    placeholder="REF-Terraform"
                />
            </label>

            <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
                Domain
                <select
                    className={FIELD_CLASSES}
                    value={domain}
                    onChange={(e) => setField('domain', e.target.value)}
                >
                    {DOMAIN_ORDER.map((d) => (
                        <option key={d} value={d}>
                            {d}
                        </option>
                    ))}
                </select>
            </label>

            <GalaxyField
                label="Galaxy (which body of knowledge this sun joins)"
                value={galaxy}
                onChange={setGalaxy}
            />

            <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
                Title (becomes the "# REF: ..." heading)
                <input
                    className={FIELD_CLASSES}
                    value={title}
                    onChange={(e) => setField('title', e.target.value)}
                    placeholder="Terraform Modules"
                />
            </label>

            <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
                Summary (the one-line "when to read this" blockquote)
                <textarea
                    className={`${FIELD_CLASSES} h-20`}
                    value={summary}
                    onChange={(e) => setField('summary', e.target.value)}
                    placeholder="When authoring Terraform modules, follow these rules."
                />
            </label>

            {error && <p className="text-xs text-destructive">{error}</p>}
            {report && !report.ok && <ValidationBanner report={report} />}

            <div className="flex gap-2">
                <Button disabled={submitting} onClick={() => void onSubmit()}>
                    {submitting ? 'Validating...' : 'Create (runs gates)'}
                </Button>
                <Button variant="outline" disabled={submitting} onClick={() => setView('map')}>
                    Cancel
                </Button>
            </div>
        </div>
    );
};
