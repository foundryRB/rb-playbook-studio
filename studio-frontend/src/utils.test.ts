import { describe, expect, it } from 'vitest';

import { cn } from '@/utils';

describe('cn', () => {
    it('merges conflicting tailwind classes, keeping the last', () => {
        expect(cn('p-2', 'p-4')).toBe('p-4');
    });

    it('drops falsy values', () => {
        expect(cn('text-sm', undefined, null, 'font-bold')).toBe('text-sm font-bold');
    });
});
