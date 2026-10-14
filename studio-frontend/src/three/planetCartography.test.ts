import { describe, expect, test } from 'vitest';
import { intent } from '@psa-department-of-engineering/vitest-intent';

import {
    CARTOGRAPHY_RESOLUTION,
    DEFAULT_CARTOGRAPHY_QUALITY,
    MAX_CRATERS,
    PERLIN_PERMUTATION_SIZE,
    buildPerlinPermutation,
    cartographyWidth,
    worldParams,
    type PlanetArchetype,
} from '@/three/planetCartography';
import { seededRandom } from '@/viewmodels/graph/scene.model';

/** An independent transcription of the improved-Perlin permutation shuffle,
 *  written from the algorithm rather than from the module under test. It is the
 *  reference the shared seam is held to: the table both the JS noise and the
 *  GPU noise read must be these bytes for any seed, or the two would draw
 *  different worlds from one seed. */
function referencePermutation(seed: number): Uint8Array {
    const rand = seededRandom(seed);
    const perm = new Uint8Array(512);
    const p = Array.from({ length: 256 }, (_, i) => i);
    for (let i = 255; i > 0; i -= 1) {
        const j = Math.floor(rand() * (i + 1));
        [p[i], p[j]] = [p[j], p[i]];
    }
    for (let i = 0; i < 512; i += 1) {
        perm[i] = p[i & 255];
    }
    return perm;
}

const SEEDS = [0, 1, 42, 1337, 0x77aa, 0x51f7, 2 ** 31, 4294967295];

describe('buildPerlinPermutation', () => {
    test('matches an independent transcription of the shuffle, byte for byte', () => {
        for (const seed of SEEDS) {
            expect(Array.from(buildPerlinPermutation(seed))).toEqual(
                Array.from(referencePermutation(seed)),
            );
        }
    });

    test('is deterministic: one seed always yields the same table', () => {
        for (const seed of SEEDS) {
            expect(Array.from(buildPerlinPermutation(seed))).toEqual(
                Array.from(buildPerlinPermutation(seed)),
            );
        }
    });

    test('is a doubled 256-value table: length 512, mirrored across the halves', () => {
        const perm = buildPerlinPermutation(1337);
        expect(perm.length).toBe(PERLIN_PERMUTATION_SIZE);
        for (let i = 0; i < 256; i += 1) {
            expect(perm[i + 256]).toBe(perm[i]);
        }
    });

    test('the first half is a permutation of 0..255 (a real shuffle)', () => {
        const first = Array.from(buildPerlinPermutation(42).slice(0, 256)).sort((a, b) => a - b);
        expect(first).toEqual(Array.from({ length: 256 }, (_, i) => i));
    });

    test('different seeds shuffle differently', () => {
        const a = Array.from(buildPerlinPermutation(1));
        const b = Array.from(buildPerlinPermutation(2));
        expect(a).not.toEqual(b);
    });
});

describe('cartography resolution dial', () => {
    test('a planet lands at the standard tier, 640 wide', () => {
        expect(DEFAULT_CARTOGRAPHY_QUALITY).toBe('standard');
        expect(cartographyWidth('standard')).toBe(640);
    });

    test('moon cartography is forged at 448', () => {
        expect(cartographyWidth('moon')).toBe(448);
    });

    test('the quality tiers grow the width monotonically', () => {
        const widths = (['moon', 'standard', 'high', 'ultra'] as const).map(cartographyWidth);
        for (let i = 1; i < widths.length; i += 1) {
            expect(widths[i]).toBeGreaterThan(widths[i - 1]);
        }
    });

    test('every tier is an even width (its half-height equirect stays integral)', () => {
        for (const width of Object.values(CARTOGRAPHY_RESOLUTION)) {
            expect(width % 2).toBe(0);
        }
    });
});

const ARCHETYPES: PlanetArchetype[] = ['terran', 'desert', 'ice', 'volcanic', 'gas', 'regolith'];

const PUMMELLED: PlanetArchetype[] = ['desert', 'volcanic', 'regolith'];

describe('worldParams', () => {
    intent('INT-UNIVERSE-005', 'draws the same world for a seed, every time', () => {
        for (const seed of SEEDS) {
            for (const archetype of ARCHETYPES) {
                const once = worldParams(seed, archetype, 640);
                const again = worldParams(seed, archetype, 640);
                expect(again).toEqual(once);
            }
        }
    });

    intent('INT-UNIVERSE-005', 'a higher tier scales the seeded draw, never redraws it', () => {
        for (const seed of SEEDS) {
            for (const archetype of ARCHETYPES) {
                const standard = worldParams(seed, archetype, cartographyWidth('standard'));
                const ultra = worldParams(seed, archetype, cartographyWidth('ultra'));
                expect(ultra.seaLevel).toBe(standard.seaLevel);
                expect(ultra.gasFamily).toBe(standard.gasFamily);
                expect(ultra.bandCount).toBe(standard.bandCount);
                expect(ultra.mountainAmp).toBe(standard.mountainAmp);
                expect(ultra.freq).toBe(standard.freq);
                expect(ultra.craters).toHaveLength(standard.craters.length);
                standard.craters.forEach((crater, i) => {
                    const grown = ultra.craters[i];
                    // The same crater, in the same place on the globe: only the
                    // texel count under it changes.
                    expect(grown.cx / cartographyWidth('ultra')).toBeCloseTo(
                        crater.cx / cartographyWidth('standard'),
                        12,
                    );
                    expect(grown.cy / cartographyWidth('ultra')).toBeCloseTo(
                        crater.cy / cartographyWidth('standard'),
                        12,
                    );
                    expect(grown.depth).toBe(crater.depth);
                });
            }
        }
    });

    test('only a terran world has a sea, and it sits near the middle of the range', () => {
        for (const seed of SEEDS) {
            expect(worldParams(seed, 'terran', 640).seaLevel).toBeGreaterThanOrEqual(0.48);
            expect(worldParams(seed, 'terran', 640).seaLevel).toBeLessThan(0.54);
            for (const archetype of ARCHETYPES.filter((a) => a !== 'terran')) {
                expect(worldParams(seed, archetype, 640).seaLevel).toBe(0);
            }
        }
    });

    test('only the pummelled archetypes are cratered, and never past the field', () => {
        for (const seed of SEEDS) {
            for (const archetype of ARCHETYPES) {
                const { craters } = worldParams(seed, archetype, 640);
                if (!PUMMELLED.includes(archetype)) {
                    expect(craters).toHaveLength(0);
                    continue;
                }
                expect(craters.length).toBeGreaterThan(0);
                expect(craters.length).toBeLessThanOrEqual(MAX_CRATERS);
            }
        }
    });

    test('a crater lands inside the map, clear of the poles', () => {
        for (const seed of SEEDS) {
            for (const archetype of PUMMELLED) {
                for (const crater of worldParams(seed, archetype, 640).craters) {
                    expect(crater.cx).toBeGreaterThanOrEqual(0);
                    expect(crater.cx).toBeLessThan(640);
                    expect(crater.cy).toBeGreaterThanOrEqual(320 * 0.08);
                    expect(crater.cy).toBeLessThan(320 * 0.92);
                    expect(crater.r).toBeGreaterThanOrEqual(3);
                    expect(crater.depth).toBeGreaterThan(0);
                }
            }
        }
    });

    test('the banding, relief and frequency dials stay in their bands', () => {
        for (const seed of SEEDS) {
            for (const archetype of ARCHETYPES) {
                const params = worldParams(seed, archetype, 640);
                expect(params.gasFamily).toBeGreaterThanOrEqual(0);
                expect(params.gasFamily).toBeLessThan(4);
                expect(params.bandCount).toBeGreaterThanOrEqual(6);
                expect(params.bandCount).toBeLessThan(14);
                expect(params.freq).toBeGreaterThanOrEqual(1.7);
                expect(params.freq).toBeLessThan(2.8);
                expect(params.mountainAmp).toBe(archetype === 'ice' ? 0.28 : 0.42);
            }
        }
    });
});
