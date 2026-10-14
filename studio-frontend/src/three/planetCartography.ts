import * as THREE from 'three';

import { seededRandom } from '@/viewmodels/graph/scene.model';

/** A world's cartography: the seeded parameters that decide what a world looks
 *  like, and the GPU forge that draws it.
 *
 *  The cartography is a pure function of a 32-bit seed and an archetype, so it
 *  is rendered where that shape belongs - a fragment shader writing into render
 *  targets. Four passes run per world at construction time (height, then the
 *  albedo, roughness and normal maps read back off it), each one draw call over
 *  an equirect map of the sphere. Resolution is a quality dial rather than a
 *  load cost: a wider target costs texels, not seconds.
 *
 *  Everything sequential and cheap stays in JS, where the seeded RNG lives: the
 *  permutation table the noise stands on, the crater field, the per-world
 *  constants, the palette ramps. Everything per-pixel is GLSL. That split is
 *  what keeps a seed drawing the same world every load: the RNG draws in a
 *  fixed order here, and the shader is a pure function of what it produces.
 *  Across GPUs the agreement is a world's worth, not a byte's - GLSL ES pins
 *  the arithmetic but allows a few ULP on the transcendentals the sphere
 *  mapping calls, so two vendors draw the same continents, not the same
 *  file. */

// -------------------------------------------------------------- determinism

/** Length of the doubled permutation table improved-Perlin noise indexes into
 *  (256 shuffled values, mirrored so `perm[i]` and `perm[i + 256]` coincide and
 *  the noise never reads out of bounds). */
export const PERLIN_PERMUTATION_SIZE = 512;

/** The shuffled improved-Perlin permutation for a seed: 256 values in a seeded
 *  Fisher-Yates order, doubled to 512. This is the ONE determinism seam the
 *  cartography stands on - the CPU noise (nebulae, rings, the shared detail
 *  normal) reads it in JS and the GPU noise reads the same bytes from a
 *  texture, so neither can drift from the other. */
export function buildPerlinPermutation(seed: number): Uint8Array {
    const rand = seededRandom(seed);
    const perm = new Uint8Array(PERLIN_PERMUTATION_SIZE);
    const p = Array.from({ length: 256 }, (_, i) => i);
    for (let i = 255; i > 0; i -= 1) {
        const j = Math.floor(rand() * (i + 1));
        [p[i], p[j]] = [p[j], p[i]];
    }
    for (let i = 0; i < PERLIN_PERMUTATION_SIZE; i += 1) {
        perm[i] = p[i & 255];
    }
    return perm;
}

// ----------------------------------------------------------- resolution dial

/** The quality tiers a world can be forged at. `moon` is the shared moon
 *  cartography, `standard` the tier every planet lands at; `high` and `ultra`
 *  are there for a world under close inspection, where a larger render target
 *  costs texels but not seconds. */
export type CartographyQuality = 'moon' | 'standard' | 'high' | 'ultra';

/** Equirect texture WIDTH per quality tier; the height is always half the
 *  width (a 2:1 equirect map of the sphere). */
export const CARTOGRAPHY_RESOLUTION: Record<CartographyQuality, number> = {
    moon: 448,
    standard: 640,
    high: 1024,
    ultra: 2048,
};

/** The tier a world is forged at on load: wide enough to read as a world from
 *  any distance the scene flies to, and modest enough that a whole corpus of
 *  worlds fits in texture memory at once. */
export const DEFAULT_CARTOGRAPHY_QUALITY: CartographyQuality = 'standard';

/** The equirect width for a quality tier. */
export function cartographyWidth(quality: CartographyQuality): number {
    return CARTOGRAPHY_RESOLUTION[quality];
}

// ---------------------------------------------------------------- archetypes

export type PlanetArchetype = 'terran' | 'desert' | 'ice' | 'volcanic' | 'gas' | 'regolith';

export interface PlanetAssets {
    map: THREE.Texture;
    normalMap: THREE.Texture;
    roughnessMap: THREE.Texture;
    archetype: PlanetArchetype;
    /** Sea presence: drives specular glint in the planet shader. */
    hasSea: boolean;
}

/** The archetype a seed wears. */
export function archetypeOf(seed: number): PlanetArchetype {
    const roll = seededRandom(seed ^ 0x9e37)();
    if (roll < 0.3) {
        return 'gas';
    }
    if (roll < 0.56) {
        return 'terran';
    }
    if (roll < 0.72) {
        return 'desert';
    }
    if (roll < 0.86) {
        return 'ice';
    }
    return 'volcanic';
}

/** The order the palette ramps sit in the lookup texture: the five solid
 *  archetypes, then the gas families. */
const SOLID_ARCHETYPES: Exclude<PlanetArchetype, 'gas'>[] = [
    'terran',
    'desert',
    'ice',
    'volcanic',
    'regolith',
];

/** The archetype's own code in GLSL, and its row in the palette texture for
 *  every archetype but gas (a gas giant's row is its family). */
const ARCHETYPE_CODE: Record<PlanetArchetype, number> = {
    terran: 0,
    desert: 1,
    ice: 2,
    volcanic: 3,
    regolith: 4,
    gas: 5,
};

// ------------------------------------------------------------------ palettes

type Stop = [number, string];

/** Hypsometric ramps: terrain wears natural elevation colours, never UI ones. */
const PALETTES: Record<Exclude<PlanetArchetype, 'gas'>, Stop[]> = {
    terran: [
        [0.0, '#04162e'],
        [0.4, '#0a2f57'],
        [0.47, '#15507f'],
        [0.5, '#d3c088'],
        [0.53, '#4d7a38'],
        [0.63, '#5d7040'],
        [0.74, '#7c7457'],
        [0.85, '#8f8d85'],
        [0.93, '#e6ebeb'],
        [1.0, '#ffffff'],
    ],
    desert: [
        [0.0, '#4c2a16'],
        [0.3, '#75401f'],
        [0.5, '#a35d2a'],
        [0.68, '#c98847'],
        [0.84, '#e0b57e'],
        [1.0, '#f2ddb8'],
    ],
    ice: [
        [0.0, '#5d92b8'],
        [0.35, '#9cc3dd'],
        [0.55, '#cfe6f2'],
        [0.8, '#ecf6fb'],
        [1.0, '#ffffff'],
    ],
    volcanic: [
        [0.0, '#0d0a08'],
        [0.3, '#231c16'],
        [0.55, '#3c3128'],
        [0.75, '#57473a'],
        [1.0, '#75655a'],
    ],
    regolith: [
        [0.0, '#3a3a3f'],
        [0.35, '#565660'],
        [0.6, '#75757d'],
        [0.82, '#96969c'],
        [1.0, '#c7c7cc'],
    ],
};

const GAS_FAMILIES: string[][] = [
    ['#8a6844', '#b98d5e', '#e8d3b0', '#c9a06b', '#a67c52', '#dcc094'],
    ['#274a7f', '#2b5f9f', '#4a7fc0', '#7fa8d9', '#3f6fb5', '#9dc0e8'],
    ['#c9b18a', '#e0cba3', '#efe3c4', '#d6bd92', '#e8d9b5', '#f2ead2'],
    ['#5f8a7a', '#7ba893', '#a3c9b5', '#8fb8a4', '#6f9b88', '#c2ddd0'],
];

/** Rows in the palette texture: one per solid archetype, then one per gas
 *  family. */
const PALETTE_ROWS = SOLID_ARCHETYPES.length + GAS_FAMILIES.length;

/** Samples per ramp. Wide enough that resampling a ramp's stops costs less
 *  than the byte the albedo lands in. */
const PALETTE_SAMPLES = 1024;

function samplePalette(stops: Stop[], t: number, out: THREE.Color): void {
    const clamped = Math.min(Math.max(t, 0), 1);
    for (let i = 1; i < stops.length; i += 1) {
        if (clamped <= stops[i][0]) {
            const [t0, c0] = stops[i - 1];
            const [t1, c1] = stops[i];
            const k = t1 === t0 ? 0 : (clamped - t0) / (t1 - t0);
            out.set(c0).lerp(new THREE.Color(c1), k);
            return;
        }
    }
    out.set(stops[stops.length - 1][1]);
}

/** A gas giant's banding runs its family as an even ramp, the last stop held
 *  flat across the top of the range. */
function sampleGasFamily(family: string[], t: number, out: THREE.Color): void {
    const clamped = Math.min(Math.max(t, 0), 1);
    const index = Math.min(Math.floor(clamped * family.length), family.length - 1);
    const next = Math.min(index + 1, family.length - 1);
    out.set(family[index]).lerp(new THREE.Color(family[next]), clamped * family.length - index);
}

/** Every ramp resampled into one lookup texture the albedo shader reads: a
 *  half-float row per palette, so a deep-ocean blue keeps its precision instead
 *  of quantising to black on the way to the GPU. */
function buildPaletteTexture(): THREE.DataTexture {
    const data = new Uint16Array(PALETTE_SAMPLES * PALETTE_ROWS * 4);
    const color = new THREE.Color();
    for (let row = 0; row < PALETTE_ROWS; row += 1) {
        const gas = row - SOLID_ARCHETYPES.length;
        for (let i = 0; i < PALETTE_SAMPLES; i += 1) {
            const t = i / (PALETTE_SAMPLES - 1);
            if (gas < 0) {
                samplePalette(PALETTES[SOLID_ARCHETYPES[row]], t, color);
            } else {
                sampleGasFamily(GAS_FAMILIES[gas], t, color);
            }
            const at = (row * PALETTE_SAMPLES + i) * 4;
            data[at] = THREE.DataUtils.toHalfFloat(color.r);
            data[at + 1] = THREE.DataUtils.toHalfFloat(color.g);
            data[at + 2] = THREE.DataUtils.toHalfFloat(color.b);
            data[at + 3] = THREE.DataUtils.toHalfFloat(1);
        }
    }
    const texture = new THREE.DataTexture(
        data,
        PALETTE_SAMPLES,
        PALETTE_ROWS,
        THREE.RGBAFormat,
        THREE.HalfFloatType,
    );
    texture.needsUpdate = true;
    return texture;
}

// --------------------------------------------------------- seeded parameters

/** A crater in texel coordinates of the world's equirect map. */
export interface Crater {
    cx: number;
    cy: number;
    r: number;
    depth: number;
}

/** The most craters a world is ever pummelled with, and the width of the
 *  texture they ride to the GPU on. */
export const MAX_CRATERS = 128;

/** Everything about a world the seed decides: the constants the shader takes
 *  as uniforms, and the crater field it stamps. Drawn in a fixed order from one
 *  seeded stream, so a seed yields this exactly once and forever. */
export interface WorldParams {
    /** Normalized height the sea reaches; zero on a world with no sea. */
    seaLevel: number;
    /** Which gas family bands the world, for a gas giant. */
    gasFamily: number;
    /** How many bands a gas giant wears. */
    bandCount: number;
    /** How tall the ridged mountains stand. */
    mountainAmp: number;
    /** Noise frequency: how large the continents come out. */
    freq: number;
    craters: Crater[];
}

/** The seeded parameters of one world. */
export function worldParams(seed: number, archetype: PlanetArchetype, width: number): WorldParams {
    const height = width / 2;
    const rand = seededRandom(seed ^ 0x77aa);
    const seaLevel = archetype === 'terran' ? 0.48 + rand() * 0.06 : 0;
    const gasFamily = Math.floor(rand() * GAS_FAMILIES.length);
    const bandCount = 6 + Math.floor(rand() * 8);
    const mountainAmp = archetype === 'ice' ? 0.28 : 0.42;
    const freq = 1.7 + rand() * 1.1;
    const craters: Crater[] = [];
    // Craters cut into the height field; regolith worlds get pummelled.
    if (archetype === 'regolith' || archetype === 'desert' || archetype === 'volcanic') {
        const count =
            archetype === 'regolith' ? 60 + Math.floor(rand() * 60) : 10 + Math.floor(rand() * 18);
        for (let i = 0; i < count; i += 1) {
            craters.push({
                cx: rand() * width,
                cy: height * (0.08 + rand() * 0.84),
                r: 3 + rand() * rand() * (width / 14),
                depth: 0.05 + rand() * 0.1,
            });
        }
    }
    return { seaLevel, gasFamily, bandCount, mountainAmp, freq, craters };
}

// --------------------------------------------------------------------- GLSL

const VERTEX_SHADER = /* glsl */ `
    varying vec2 vUv;
    void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
`;

/** Improved-Perlin gradient noise reading the same seeded permutation the JS
 *  noise reads, one row per generator, plus the fBm and ridged-multifractal
 *  stacks built on it and the equirect-to-sphere mapping every pass shares. */
const NOISE_CHUNK = /* glsl */ `
    #define PI 3.141592653589793
    #define PERM_TERRAIN 0.0
    #define PERM_WARP 1.0
    #define PERM_GRAIN 2.0

    uniform sampler2D uPermutation;
    uniform vec2 uSize;

    float permAt(float i, float row) {
        vec2 uv = vec2((mod(i, 256.0) + 0.5) / 256.0, (row + 0.5) / 3.0);
        return floor(texture2D(uPermutation, uv).r * 255.0 + 0.5);
    }

    float fade(float t) {
        return t * t * t * (t * (t * 6.0 - 15.0) + 10.0);
    }

    float grad3(float hash, vec3 p) {
        float h = mod(hash, 16.0);
        float u = h < 8.0 ? p.x : p.y;
        float v = h < 4.0 ? p.y : ((h == 12.0 || h == 14.0) ? p.x : p.z);
        return (mod(h, 2.0) < 0.5 ? u : -u) + (mod(floor(h * 0.5), 2.0) < 0.5 ? v : -v);
    }

    float noise3(vec3 p, float row) {
        vec3 cell = floor(p);
        float X = mod(cell.x, 256.0);
        float Y = mod(cell.y, 256.0);
        float Z = mod(cell.z, 256.0);
        vec3 f = p - cell;
        float u = fade(f.x);
        float v = fade(f.y);
        float w = fade(f.z);
        float A = permAt(X, row) + Y;
        float AA = permAt(A, row) + Z;
        float AB = permAt(A + 1.0, row) + Z;
        float B = permAt(X + 1.0, row) + Y;
        float BA = permAt(B, row) + Z;
        float BB = permAt(B + 1.0, row) + Z;
        return mix(
            mix(
                mix(grad3(permAt(AA, row), f),
                    grad3(permAt(BA, row), f - vec3(1.0, 0.0, 0.0)), u),
                mix(grad3(permAt(AB, row), f - vec3(0.0, 1.0, 0.0)),
                    grad3(permAt(BB, row), f - vec3(1.0, 1.0, 0.0)), u),
                v),
            mix(
                mix(grad3(permAt(AA + 1.0, row), f - vec3(0.0, 0.0, 1.0)),
                    grad3(permAt(BA + 1.0, row), f - vec3(1.0, 0.0, 1.0)), u),
                mix(grad3(permAt(AB + 1.0, row), f - vec3(0.0, 1.0, 1.0)),
                    grad3(permAt(BB + 1.0, row), f - vec3(1.0, 1.0, 1.0)), u),
                v),
            w);
    }

    float fbm3(vec3 p, float row, int octaves) {
        float value = 0.0;
        float amplitude = 0.5;
        float frequency = 1.0;
        for (int i = 0; i < 8; i++) {
            if (i >= octaves) { break; }
            value += amplitude * noise3(p * frequency, row);
            amplitude *= 0.5;
            frequency *= 2.03;
        }
        return value;
    }

    /** Ridged multifractal: sharp mountain crests instead of soft blobs. */
    float ridged3(vec3 p, float row, int octaves) {
        float value = 0.0;
        float amplitude = 0.55;
        float frequency = 1.0;
        for (int i = 0; i < 8; i++) {
            if (i >= octaves) { break; }
            float n = 1.0 - abs(noise3(p * frequency, row));
            value += amplitude * n * n;
            amplitude *= 0.52;
            frequency *= 2.1;
        }
        return value;
    }

    /** The texel this fragment stands for, in the row-major grid the world is
     *  indexed by: row zero is the north pole, and a texture's v axis climbs
     *  the other way. */
    vec2 texelOf(vec2 uv) {
        return vec2(floor(uv.x * uSize.x), floor((1.0 - uv.y) * uSize.y));
    }

    /** Where a texel sits on the unit sphere: no equirect pinch, because the
     *  noise is sampled in three dimensions. */
    void sphereAt(vec2 texel, out float sinPhi, out float cosPhi, out vec3 unit) {
        float phi = (texel.y / (uSize.y - 1.0)) * PI;
        sinPhi = sin(phi);
        cosPhi = cos(phi);
        float theta = (texel.x / uSize.x) * PI * 2.0;
        unit = vec3(sinPhi * cos(theta), cosPhi, sinPhi * sin(theta));
    }
`;

/** The height field's normalization, shared by every pass that reads it: the
 *  raw field's own range, reduced to a single texel, maps it onto [0, 1].
 *
 *  The range is the extrema of the TEXELS SAMPLED, not of the continuous
 *  elevation function, so it is a property of the tier as much as of the seed:
 *  a finer grid finds slightly wider extrema and every normalized height
 *  shifts with them. At a fixed tier a seed is exact, which is what the scene
 *  and the rigs stand on. Re-forging one world at a higher tier moves its
 *  coastline by a fraction of the terran palette's coastal band, so an LOD
 *  that swaps tiers under a camera owes that a fixed reference range. */
const HEIGHT_READ_CHUNK = /* glsl */ `
    uniform sampler2D uHeight;
    uniform sampler2D uRange;

    float heightAt(vec2 uv) {
        vec2 range = texture2D(uRange, vec2(0.5)).rg;
        return (texture2D(uHeight, uv).r - range.x) / max(range.y - range.x, 1e-6);
    }
`;

/** Sphere-sampled elevation: domain-warped continents with ridged mountains
 *  above the waterline, or banding for a gas giant, with craters cut in. */
const HEIGHT_SHADER = /* glsl */ `
    varying vec2 vUv;
    uniform float uFreq;
    uniform float uSeaLevel;
    uniform float uMountainAmp;
    uniform float uBandCount;
    uniform int uArchetype;
    uniform sampler2D uCraters;
    uniform int uCraterCount;

    void main() {
        vec2 texel = texelOf(vUv);
        float sinPhi;
        float cosPhi;
        vec3 unit;
        sphereAt(texel, sinPhi, cosPhi, unit);
        vec3 p = unit * uFreq;
        float h;
        if (uArchetype == 5) {
            float swirl = fbm3(p * 0.9, PERM_WARP, 4) * 0.9;
            float band = sin((cosPhi + swirl * 0.35) * PI * (uBandCount / 2.0));
            h = 0.5 + band * 0.3 + fbm3(p * 2.4, PERM_TERRAIN, 4) * 0.12;
        } else {
            vec3 warped = p + 0.7 * vec3(
                fbm3(p, PERM_WARP, 3),
                fbm3(p + vec3(5.2, 1.3, 2.8), PERM_WARP, 3),
                fbm3(p + vec3(9.1, 4.7, 7.4), PERM_WARP, 3));
            float continents = fbm3(warped, PERM_TERRAIN, 6) * 0.75 + 0.5;
            float mountains = ridged3(warped * 2.2, PERM_TERRAIN, 5);
            float landMask = clamp((continents - uSeaLevel + 0.08) * 4.0, 0.0, 1.0);
            h = (continents + mountains * uMountainAmp * landMask) * 0.62;
        }
        for (int i = 0; i < ${MAX_CRATERS}; i++) {
            if (i >= uCraterCount) { break; }
            vec4 crater = texture2D(uCraters, vec2((float(i) + 0.5) / ${MAX_CRATERS}.0, 0.5));
            float dx = texel.x - crater.x;
            dx -= uSize.x * floor(dx / uSize.x + 0.5);
            float dy = texel.y - crater.y;
            float reach = crater.z + 2.0;
            if (abs(dx) > reach || abs(dy) > reach) { continue; }
            float d = length(vec2(dx, dy)) / crater.z;
            if (d > 1.15) { continue; }
            if (d < 0.85) {
                // Bowl: deepest at centre, flat floor.
                h -= crater.w * (1.0 - d * d * 0.65);
            } else {
                // Raised rim with a soft outer skirt.
                float rim = exp(-((d - 0.95) * (d - 0.95)) / 0.006);
                h += crater.w * 0.55 * rim;
            }
        }
        gl_FragColor = vec4(h, 0.0, 0.0, 1.0);
    }
`;

/** One step of the range reduction: a 4x4 block of the source folded into the
 *  minimum and maximum it holds, run until the whole field is one texel. */
const RANGE_SHADER = /* glsl */ `
    varying vec2 vUv;
    uniform sampler2D uSource;
    uniform vec2 uSourceSize;
    uniform vec2 uDestSize;
    uniform float uFirst;

    void main() {
        vec2 dest = floor(vUv * uDestSize);
        vec2 range = vec2(1e4, -1e4);
        for (int j = 0; j < 4; j++) {
            for (int i = 0; i < 4; i++) {
                vec2 at = min(dest * 4.0 + vec2(float(i), float(j)), uSourceSize - 1.0);
                vec4 texel = texture2D(uSource, (at + 0.5) / uSourceSize);
                vec2 pair = uFirst > 0.5 ? vec2(texel.r) : texel.rg;
                range = vec2(min(range.x, pair.x), max(range.y, pair.y));
            }
        }
        gl_FragColor = vec4(range, 0.0, 1.0);
    }
`;

/** Three's own sRGB decode and the HSL round trip `Color.offsetHSL` runs, so a
 *  colour the shader lands is the colour the palette names. */
const COLOR_CHUNK = /* glsl */ `
    uniform sampler2D uPalette;
    uniform float uPaletteRow;

    vec3 paletteAt(float t) {
        float x = clamp(t, 0.0, 1.0) * ${PALETTE_SAMPLES - 1}.0;
        float i0 = floor(x);
        float i1 = min(i0 + 1.0, ${PALETTE_SAMPLES - 1}.0);
        float row = (uPaletteRow + 0.5) / ${PALETTE_ROWS}.0;
        vec3 c0 = texture2D(uPalette, vec2((i0 + 0.5) / ${PALETTE_SAMPLES}.0, row)).rgb;
        vec3 c1 = texture2D(uPalette, vec2((i1 + 0.5) / ${PALETTE_SAMPLES}.0, row)).rgb;
        return mix(c0, c1, x - i0);
    }

    float hue2rgb(float p, float q, float t) {
        if (t < 0.0) { t += 1.0; }
        if (t > 1.0) { t -= 1.0; }
        if (t < 1.0 / 6.0) { return p + (q - p) * 6.0 * t; }
        if (t < 0.5) { return q; }
        if (t < 2.0 / 3.0) { return p + (q - p) * 6.0 * (2.0 / 3.0 - t); }
        return p;
    }

    /** The colour with its HSL lightness nudged: fine grain, so a close-up
     *  never looks airbrushed. */
    vec3 offsetLightness(vec3 c, float delta) {
        float high = max(max(c.r, c.g), c.b);
        float low = min(min(c.r, c.g), c.b);
        float lightness = (low + high) * 0.5;
        float hue = 0.0;
        float saturation = 0.0;
        if (low != high) {
            float spread = high - low;
            saturation = lightness <= 0.5
                ? spread / (high + low)
                : spread / (2.0 - high - low);
            if (high == c.r) {
                hue = (c.g - c.b) / spread + (c.g < c.b ? 6.0 : 0.0);
            } else if (high == c.g) {
                hue = (c.b - c.r) / spread + 2.0;
            } else {
                hue = (c.r - c.g) / spread + 4.0;
            }
            hue /= 6.0;
        }
        float l = clamp(lightness + delta, 0.0, 1.0);
        if (saturation <= 0.0) {
            return vec3(l);
        }
        float p = l <= 0.5 ? l * (1.0 + saturation) : l + saturation - (l * saturation);
        float q = 2.0 * l - p;
        return vec3(
            hue2rgb(q, p, hue + 1.0 / 3.0),
            hue2rgb(q, p, hue),
            hue2rgb(q, p, hue - 1.0 / 3.0));
    }

    vec3 srgbToLinear(vec3 c) {
        return mix(
            pow(c * 0.9478672986 + 0.0521327014, vec3(2.4)),
            c * 0.0773993808,
            vec3(lessThanEqual(c, vec3(0.04045))));
    }
`;

/** Hypsometric albedo: the palette the height wears, with ice caps, ice cracks
 *  and ember veins on the archetypes that carry them. */
const ALBEDO_SHADER = /* glsl */ `
    varying vec2 vUv;
    uniform int uArchetype;
    uniform float uNormSea;
    uniform vec3 uCapColor;
    uniform vec3 uCrackColor;
    uniform vec3 uEmberColor;

    void main() {
        vec2 texel = texelOf(vUv);
        float h = heightAt(vUv);
        float lat = abs(texel.y / (uSize.y - 1.0) - 0.5) * 2.0;
        float sinPhi;
        float cosPhi;
        vec3 unit;
        sphereAt(texel, sinPhi, cosPhi, unit);
        vec3 color = paletteAt(h);
        if (uArchetype == 0 && h >= uNormSea && (lat > 0.82 || h > 0.9)) {
            // Snow and ice caps, ragged by the terrain itself.
            float capBlend = clamp((lat - 0.82) / 0.1 + (h - 0.55), 0.0, 1.0);
            color = mix(color, uCapColor, capBlend);
        }
        if (uArchetype == 2) {
            float crack = ridged3(unit * 7.0, PERM_TERRAIN, 3);
            if (crack > 1.02) {
                color = mix(color, uCrackColor, min((crack - 1.02) * 5.0, 0.6));
            }
        }
        if (uArchetype == 3 && h < 0.3) {
            // Ember veins glowing in the lowlands.
            float vein = ridged3(unit * 9.0, PERM_TERRAIN, 3);
            if (vein > 1.08) {
                color = mix(color, uEmberColor, min((vein - 1.08) * 6.0, 0.9));
            }
        }
        color = offsetLightness(color, noise3(unit * 40.0, PERM_GRAIN) * 0.05);
        // The attachment is sRGB, so it encodes on write: emitting the decoded
        // colour stores the working-space component the planet shader samples
        // back, and stores it with sRGB's precision in the darks.
        gl_FragColor = vec4(srgbToLinear(clamp(color, 0.0, 1.0)), 1.0);
    }
`;

/** Roughness read off the terrain: water is glassy, caps and cracked ice are
 *  half-rough, and ember veins polish the lava they run through. */
const ROUGHNESS_SHADER = /* glsl */ `
    varying vec2 vUv;
    uniform int uArchetype;
    uniform float uNormSea;

    void main() {
        vec2 texel = texelOf(vUv);
        float h = heightAt(vUv);
        float lat = abs(texel.y / (uSize.y - 1.0) - 0.5) * 2.0;
        float sinPhi;
        float cosPhi;
        vec3 unit;
        sphereAt(texel, sinPhi, cosPhi, unit);
        float roughness = 0.85;
        if (uArchetype == 5) {
            roughness = 0.55;
        } else {
            if (uArchetype == 0) {
                if (h < uNormSea) {
                    roughness = 0.24 + h * 0.2;
                } else if (lat > 0.82 || h > 0.9) {
                    roughness = 0.5;
                }
            }
            if (uArchetype == 2) {
                roughness = 0.32;
            }
            if (uArchetype == 3 && h < 0.3) {
                float vein = ridged3(unit * 9.0, PERM_TERRAIN, 3);
                if (vein > 1.08) {
                    roughness = 0.4;
                }
            }
        }
        float grain = noise3(unit * 40.0, PERM_GRAIN) * 0.05;
        gl_FragColor = vec4(vec3(clamp(roughness + grain, 0.05, 1.0)), 1.0);
    }
`;

/** Sobel normals off the height field (x wraps the globe, y stops at the
 *  poles), so crater rims catch the light. */
const NORMAL_SHADER = /* glsl */ `
    varying vec2 vUv;
    uniform float uStrength;

    void main() {
        vec2 texel = vec2(1.0 / uSize.x, 1.0 / uSize.y);
        float left = heightAt(vUv - vec2(texel.x, 0.0));
        float right = heightAt(vUv + vec2(texel.x, 0.0));
        float up = heightAt(vUv + vec2(0.0, texel.y));
        float down = heightAt(vUv - vec2(0.0, texel.y));
        float dx = (right - left) * uStrength;
        float dy = (down - up) * uStrength;
        float inv = 1.0 / length(vec3(dx, dy, 1.0));
        gl_FragColor = vec4(-dx * inv * 0.5 + 0.5, -dy * inv * 0.5 + 0.5, inv * 0.5 + 0.5, 1.0);
    }
`;

// ---------------------------------------------------------------- the forge

function dataTexture(
    data: THREE.TypedArray,
    width: number,
    height: number,
    format: THREE.PixelFormat,
    type: THREE.TextureDataType,
): THREE.DataTexture {
    const texture = new THREE.DataTexture(data, width, height, format, type);
    texture.needsUpdate = true;
    return texture;
}

/** Forges a world's cartography on the GPU: one renderer's worth of shared
 *  shaders, scratch targets and lookup textures, and a map set per world.
 *
 *  The forge owns every render target it hands out, so disposing it frees the
 *  whole corpus of worlds in one act. */
export class PlanetForge {
    private readonly renderer: THREE.WebGLRenderer;
    private readonly geometry: THREE.BufferGeometry;
    private readonly camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    private readonly quad: THREE.Mesh;
    private readonly palette: THREE.DataTexture;
    private readonly permutation: THREE.DataTexture;
    private readonly permutationData: Uint8Array;
    private readonly craters: THREE.DataTexture;
    private readonly craterData: Float32Array;
    private readonly heightMaterial: THREE.ShaderMaterial;
    private readonly rangeMaterial: THREE.ShaderMaterial;
    private readonly albedoMaterial: THREE.ShaderMaterial;
    private readonly roughnessMaterial: THREE.ShaderMaterial;
    private readonly normalMaterial: THREE.ShaderMaterial;
    /** Scratch height fields and range-reduction chains, one per width forged. */
    private readonly heightTargets = new Map<number, THREE.WebGLRenderTarget>();
    private readonly rangeChains = new Map<number, THREE.WebGLRenderTarget[]>();
    /** Every map handed out, held so the forge can free them all. */
    private readonly forged: THREE.WebGLRenderTarget[] = [];
    private readonly fieldType: THREE.TextureDataType;

    constructor(renderer: THREE.WebGLRenderer) {
        this.renderer = renderer;
        // A full-viewport triangle: one draw call per pass, no seam down the
        // middle of a quad.
        this.geometry = new THREE.BufferGeometry();
        this.geometry.setAttribute(
            'position',
            new THREE.Float32BufferAttribute([-1, 3, 0, -1, -1, 0, 3, -1, 0], 3),
        );
        this.geometry.setAttribute('uv', new THREE.Float32BufferAttribute([0, 2, 0, 0, 2, 0], 2));

        this.palette = buildPaletteTexture();
        this.permutationData = new Uint8Array(256 * 3);
        this.permutation = dataTexture(
            this.permutationData,
            256,
            3,
            THREE.RedFormat,
            THREE.UnsignedByteType,
        );
        this.craterData = new Float32Array(MAX_CRATERS * 4);
        this.craters = dataTexture(
            this.craterData,
            MAX_CRATERS,
            1,
            THREE.RGBAFormat,
            THREE.FloatType,
        );
        // The height field carries derivatives a Sobel pass reads back, so it
        // wants every bit the renderer can render into.
        this.fieldType = renderer.extensions.has('EXT_color_buffer_float')
            ? THREE.FloatType
            : THREE.HalfFloatType;

        // Fresh holders per material: a spread of one literal would copy the
        // keys but share the { value } objects, quietly coupling four programs
        // to one another's uniforms.
        const shared = (): Record<string, THREE.IUniform> => ({
            uPermutation: { value: this.permutation },
            uSize: { value: new THREE.Vector2() },
        });
        this.heightMaterial = new THREE.ShaderMaterial({
            uniforms: {
                ...shared(),
                uFreq: { value: 0 },
                uSeaLevel: { value: 0 },
                uMountainAmp: { value: 0 },
                uBandCount: { value: 0 },
                uArchetype: { value: 0 },
                uCraters: { value: this.craters as THREE.Texture },
                uCraterCount: { value: 0 },
            },
            vertexShader: VERTEX_SHADER,
            fragmentShader: NOISE_CHUNK + HEIGHT_SHADER,
        });
        this.rangeMaterial = new THREE.ShaderMaterial({
            uniforms: {
                uSource: { value: null },
                uSourceSize: { value: new THREE.Vector2() },
                uDestSize: { value: new THREE.Vector2() },
                uFirst: { value: 0 },
            },
            vertexShader: VERTEX_SHADER,
            fragmentShader: RANGE_SHADER,
        });
        const field = (): Record<string, THREE.IUniform> => ({
            uHeight: { value: null },
            uRange: { value: null },
        });
        this.albedoMaterial = new THREE.ShaderMaterial({
            uniforms: {
                ...shared(),
                ...field(),
                uPalette: { value: this.palette as THREE.Texture },
                uPaletteRow: { value: 0 },
                uArchetype: { value: 0 },
                uNormSea: { value: 0 },
                uCapColor: { value: new THREE.Color('#f2f6f7') },
                uCrackColor: { value: new THREE.Color('#3e7ba6') },
                uEmberColor: { value: new THREE.Color('#ff4d13') },
            },
            vertexShader: VERTEX_SHADER,
            fragmentShader: NOISE_CHUNK + HEIGHT_READ_CHUNK + COLOR_CHUNK + ALBEDO_SHADER,
        });
        this.roughnessMaterial = new THREE.ShaderMaterial({
            uniforms: {
                ...shared(),
                ...field(),
                uArchetype: { value: 0 },
                uNormSea: { value: 0 },
            },
            vertexShader: VERTEX_SHADER,
            fragmentShader: NOISE_CHUNK + HEIGHT_READ_CHUNK + ROUGHNESS_SHADER,
        });
        this.normalMaterial = new THREE.ShaderMaterial({
            uniforms: {
                ...shared(),
                ...field(),
                uStrength: { value: 0 },
            },
            vertexShader: VERTEX_SHADER,
            fragmentShader: NOISE_CHUNK + HEIGHT_READ_CHUNK + NORMAL_SHADER,
        });
        // Each pass assigns its own material before it draws; the mesh borrows
        // one here rather than having three.js mint a default it would orphan.
        this.quad = new THREE.Mesh(this.geometry, this.heightMaterial);
    }

    /** Full asset set for one world: the height field forged first, then the
     *  albedo, roughness and normal maps read off it. */
    forge(
        seed: number,
        archetype: PlanetArchetype,
        width: number = cartographyWidth(DEFAULT_CARTOGRAPHY_QUALITY),
    ): PlanetAssets {
        const height = width / 2;
        const params = worldParams(seed, archetype, width);
        const code = ARCHETYPE_CODE[archetype];
        const previous = this.renderer.getRenderTarget();

        this.loadPermutations(seed);
        this.loadCraters(params.craters);

        const heightTarget = this.heightTarget(width, height);
        const size = new THREE.Vector2(width, height);
        const heightUniforms = this.heightMaterial.uniforms;
        heightUniforms.uSize.value.copy(size);
        heightUniforms.uFreq.value = params.freq;
        heightUniforms.uSeaLevel.value = params.seaLevel;
        heightUniforms.uMountainAmp.value = params.mountainAmp;
        heightUniforms.uBandCount.value = params.bandCount;
        heightUniforms.uArchetype.value = code;
        heightUniforms.uCraterCount.value = params.craters.length;
        this.draw(this.heightMaterial, heightTarget);

        const range = this.reduceRange(width, height, heightTarget);

        const paletteRow = archetype === 'gas' ? SOLID_ARCHETYPES.length + params.gasFamily : code;
        const normSea = archetype === 'terran' ? 0.5 : 0;

        const albedo = this.mapTarget(width, height, THREE.SRGBColorSpace, 8);
        const albedoUniforms = this.albedoMaterial.uniforms;
        albedoUniforms.uSize.value.copy(size);
        albedoUniforms.uHeight.value = heightTarget.texture;
        albedoUniforms.uRange.value = range.texture;
        albedoUniforms.uPaletteRow.value = paletteRow;
        albedoUniforms.uArchetype.value = code;
        albedoUniforms.uNormSea.value = normSea;
        this.draw(this.albedoMaterial, albedo);

        const rough = this.mapTarget(width, height, THREE.NoColorSpace, 1);
        const roughUniforms = this.roughnessMaterial.uniforms;
        roughUniforms.uSize.value.copy(size);
        roughUniforms.uHeight.value = heightTarget.texture;
        roughUniforms.uRange.value = range.texture;
        roughUniforms.uArchetype.value = code;
        roughUniforms.uNormSea.value = normSea;
        this.draw(this.roughnessMaterial, rough);

        const normal = this.mapTarget(width, height, THREE.NoColorSpace, 4);
        const normalUniforms = this.normalMaterial.uniforms;
        normalUniforms.uSize.value.copy(size);
        normalUniforms.uHeight.value = heightTarget.texture;
        normalUniforms.uRange.value = range.texture;
        // A gas giant's banding is painted, not sculpted, so it stays flat.
        normalUniforms.uStrength.value = archetype === 'gas' ? 0.6 : 2.6;
        this.draw(this.normalMaterial, normal);

        this.renderer.setRenderTarget(previous);
        return {
            map: albedo.texture,
            normalMap: normal.texture,
            roughnessMap: rough.texture,
            archetype,
            hasSea: archetype === 'terran',
        };
    }

    /** Frees every world this forge drew, along with its shared scratch. */
    dispose(): void {
        for (const target of this.forged) {
            target.dispose();
        }
        this.forged.length = 0;
        for (const target of this.heightTargets.values()) {
            target.dispose();
        }
        this.heightTargets.clear();
        for (const chain of this.rangeChains.values()) {
            for (const target of chain) {
                target.dispose();
            }
        }
        this.rangeChains.clear();
        this.palette.dispose();
        this.permutation.dispose();
        this.craters.dispose();
        this.heightMaterial.dispose();
        this.rangeMaterial.dispose();
        this.albedoMaterial.dispose();
        this.roughnessMaterial.dispose();
        this.normalMaterial.dispose();
        this.geometry.dispose();
    }

    private draw(material: THREE.ShaderMaterial, target: THREE.WebGLRenderTarget): void {
        this.quad.material = material;
        this.renderer.setRenderTarget(target);
        this.renderer.render(this.quad, this.camera);
    }

    /** The three seeded noise streams a world reads, in the rows the shader
     *  names: terrain, the domain warp that bends it, and the surface grain. */
    private loadPermutations(seed: number): void {
        const rows = [seed, seed ^ 0x51f7, seed ^ 0x1234];
        for (let row = 0; row < rows.length; row += 1) {
            this.permutationData.set(buildPerlinPermutation(rows[row]).subarray(0, 256), row * 256);
        }
        this.permutation.needsUpdate = true;
    }

    private loadCraters(craters: Crater[]): void {
        this.craterData.fill(0);
        for (let i = 0; i < Math.min(craters.length, MAX_CRATERS); i += 1) {
            const crater = craters[i];
            this.craterData.set([crater.cx, crater.cy, crater.r, crater.depth], i * 4);
        }
        this.craters.needsUpdate = true;
    }

    /** The raw height field's own minimum and maximum, folded 4x4 at a time
     *  until one texel holds the range the maps normalize against. */
    private reduceRange(
        width: number,
        height: number,
        source: THREE.WebGLRenderTarget,
    ): THREE.WebGLRenderTarget {
        const chain = this.rangeChain(width, height);
        const uniforms = this.rangeMaterial.uniforms;
        let from: THREE.WebGLRenderTarget = source;
        let fromWidth = width;
        let fromHeight = height;
        for (let step = 0; step < chain.length; step += 1) {
            const target = chain[step];
            uniforms.uSource.value = from.texture;
            uniforms.uSourceSize.value.set(fromWidth, fromHeight);
            uniforms.uDestSize.value.set(target.width, target.height);
            uniforms.uFirst.value = step === 0 ? 1 : 0;
            this.draw(this.rangeMaterial, target);
            from = target;
            fromWidth = target.width;
            fromHeight = target.height;
        }
        return chain[chain.length - 1];
    }

    private heightTarget(width: number, height: number): THREE.WebGLRenderTarget {
        const held = this.heightTargets.get(width);
        if (held) {
            return held;
        }
        const target = new THREE.WebGLRenderTarget(width, height, {
            depthBuffer: false,
            format: THREE.RGBAFormat,
            type: this.fieldType,
            minFilter: THREE.NearestFilter,
            magFilter: THREE.NearestFilter,
            // The globe wraps in longitude and stops at the poles, so the Sobel
            // pass reads its neighbours right at the seam and the caps.
            wrapS: THREE.RepeatWrapping,
            wrapT: THREE.ClampToEdgeWrapping,
        });
        this.heightTargets.set(width, target);
        return target;
    }

    private rangeChain(width: number, height: number): THREE.WebGLRenderTarget[] {
        const held = this.rangeChains.get(width);
        if (held) {
            return held;
        }
        const chain: THREE.WebGLRenderTarget[] = [];
        let w = width;
        let h = height;
        while (w > 1 || h > 1) {
            w = Math.ceil(w / 4);
            h = Math.ceil(h / 4);
            chain.push(
                new THREE.WebGLRenderTarget(w, h, {
                    depthBuffer: false,
                    format: THREE.RGBAFormat,
                    type: this.fieldType,
                    minFilter: THREE.NearestFilter,
                    magFilter: THREE.NearestFilter,
                }),
            );
        }
        this.rangeChains.set(width, chain);
        return chain;
    }

    private mapTarget(
        width: number,
        height: number,
        colorSpace: THREE.ColorSpace,
        anisotropy: number,
    ): THREE.WebGLRenderTarget {
        const target = new THREE.WebGLRenderTarget(width, height, {
            depthBuffer: false,
            format: THREE.RGBAFormat,
            type: THREE.UnsignedByteType,
            colorSpace,
            anisotropy,
            magFilter: THREE.LinearFilter,
            minFilter: THREE.LinearMipmapLinearFilter,
            generateMipmaps: true,
        });
        this.forged.push(target);
        return target;
    }
}
