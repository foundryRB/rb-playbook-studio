import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/** Merge Tailwind class names, resolving conflicts. */
export function cn(...inputs: ClassValue[]): string {
    return twMerge(clsx(inputs));
}

/** The emails an owners field names, split on spaces and commas. */
export const parseOwners = (text: string): string[] =>
    text
        .split(/[\s,]+/)
        .map((owner) => owner.trim())
        .filter((owner) => owner.length > 0);

export interface GateResult<T> {
    ok: T | null;
    report: unknown | null;
    error: string | null;
}

/** Send a gated write; surfaces the validation report carried by a 422 rejection. */
export async function gatedSend<T>(
    url: string,
    method: 'PUT' | 'POST',
    payload: object,
): Promise<GateResult<T>> {
    const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (response.ok) {
        return { ok: (await response.json()) as T, report: null, error: null };
    }
    let rejection: { detail?: string; report?: unknown } = {};
    try {
        rejection = (await response.json()) as { detail?: string; report?: unknown };
    } catch {
        // Non-JSON error body; fall through to the status text.
    }
    return {
        ok: null,
        report: rejection.report ?? null,
        error: rejection.detail ?? `${response.status} ${response.statusText}`,
    };
}

/** Fetch JSON from the API, throwing an Error with the server-provided detail on failure. */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(path, {
        headers: { 'Content-Type': 'application/json' },
        ...init,
    });
    if (!response.ok) {
        let detail = `${response.status} ${response.statusText}`;
        try {
            const body = (await response.json()) as { detail?: string; error?: string };
            detail = body.detail ?? body.error ?? detail;
        } catch {
            // Non-JSON error body; keep the status text.
        }
        throw new Error(detail);
    }
    return (await response.json()) as T;
}
