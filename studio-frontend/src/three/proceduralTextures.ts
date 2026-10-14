import * as THREE from 'three';

import { buildPerlinPermutation, type PlanetAssets } from '@/three/planetCartography';
import { seededRandom } from '@/viewmodels/graph/scene.model';

/** Procedural celestial assets, done with the techniques real space scenes
 *  use: seeded 3D gradient noise sampled ON THE SPHERE (no equirect pinch), a
 *  shared tiling detail normal for crisp close-ups, spiked astrophoto coronas,
 *  fBm nebula clouds, dusty ring bands, dithered glows, and the shaders that
 *  light a sun, a world and a portal. Everything is deterministic per name;
 *  nothing downloads. A world's own cartography is forged on the GPU next door
 *  (`planetCartography`). */

// ---------------------------------------------------------------- 3D noise

/** Seeded improved-Perlin 3D gradient noise in [-1, 1]. The shuffled
 *  permutation is built by `planetCartography.buildPerlinPermutation` - the one
 *  determinism seam this noise shares with the GPU cartography. */
function makeNoise3D(seed: number): (x: number, y: number, z: number) => number {
    const perm = buildPerlinPermutation(seed);
    const fade = (t: number): number => t * t * t * (t * (t * 6 - 15) + 10);
    const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;
    const grad = (hash: number, x: number, y: number, z: number): number => {
        const h = hash & 15;
        const u = h < 8 ? x : y;
        const v = h < 4 ? y : h === 12 || h === 14 ? x : z;
        return ((h & 1) === 0 ? u : -u) + ((h & 2) === 0 ? v : -v);
    };
    return (x, y, z) => {
        const X = Math.floor(x) & 255;
        const Y = Math.floor(y) & 255;
        const Z = Math.floor(z) & 255;
        x -= Math.floor(x);
        y -= Math.floor(y);
        z -= Math.floor(z);
        const u = fade(x);
        const v = fade(y);
        const w = fade(z);
        const A = perm[X] + Y;
        const AA = perm[A] + Z;
        const AB = perm[A + 1] + Z;
        const B = perm[X + 1] + Y;
        const BA = perm[B] + Z;
        const BB = perm[B + 1] + Z;
        return lerp(
            lerp(
                lerp(grad(perm[AA], x, y, z), grad(perm[BA], x - 1, y, z), u),
                lerp(grad(perm[AB], x, y - 1, z), grad(perm[BB], x - 1, y - 1, z), u),
                v,
            ),
            lerp(
                lerp(grad(perm[AA + 1], x, y, z - 1), grad(perm[BA + 1], x - 1, y, z - 1), u),
                lerp(
                    grad(perm[AB + 1], x, y - 1, z - 1),
                    grad(perm[BB + 1], x - 1, y - 1, z - 1),
                    u,
                ),
                v,
            ),
            w,
        );
    };
}

type Noise3 = (x: number, y: number, z: number) => number;

function fbm3(noise: Noise3, x: number, y: number, z: number, octaves: number): number {
    let value = 0;
    let amplitude = 0.5;
    let frequency = 1;
    for (let i = 0; i < octaves; i += 1) {
        value += amplitude * noise(x * frequency, y * frequency, z * frequency);
        amplitude *= 0.5;
        frequency *= 2.03;
    }
    return value;
}

/** One shared, tiling micro-relief normal map: close-ups stay crisp without
 *  gigantic unique textures. */
export function makeDetailNormal(seed = 0xd37a11): THREE.CanvasTexture {
    const size = 256;
    const noise = makeNoise3D(seed);
    const heights = new Float32Array(size * size);
    for (let y = 0; y < size; y += 1) {
        for (let x = 0; x < size; x += 1) {
            // Sample on a torus so the tile is seamless in both axes.
            const a = (x / size) * Math.PI * 2;
            const b = (y / size) * Math.PI * 2;
            const px = Math.cos(a) * 1.4;
            const py = Math.sin(a) * 1.4;
            const pz = Math.cos(b) * 1.4;
            const pw = Math.sin(b) * 1.4;
            heights[y * size + x] =
                fbm3(noise, px + pz, py + pw, px * pw, 5) * 0.6 +
                Math.abs(noise((px + pw) * 6, (py + pz) * 6, px * 2)) * 0.4;
        }
    }
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d')!;
    const img = ctx.createImageData(size, size);
    for (let y = 0; y < size; y += 1) {
        for (let x = 0; x < size; x += 1) {
            const xL = (x - 1 + size) % size;
            const xR = (x + 1) % size;
            const yU = (y - 1 + size) % size;
            const yD = (y + 1) % size;
            const dx = (heights[y * size + xR] - heights[y * size + xL]) * 1.8;
            const dy = (heights[yD * size + x] - heights[yU * size + x]) * 1.8;
            const inv = 1 / Math.hypot(dx, dy, 1);
            const i = (y * size + x) * 4;
            img.data[i] = Math.round((-dx * inv * 0.5 + 0.5) * 255);
            img.data[i + 1] = Math.round((-dy * inv * 0.5 + 0.5) * 255);
            img.data[i + 2] = Math.round((inv * 0.5 + 0.5) * 255);
            img.data[i + 3] = 255;
        }
    }
    ctx.putImageData(img, 0, 0);
    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    return texture;
}

// -------------------------------------------------------- glow sprites

/** Soft round particle sprite with dithered falloff (no banding rings). */
export function makeParticleSprite(): THREE.CanvasTexture {
    const canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 64;
    const ctx = canvas.getContext('2d')!;
    const img = ctx.createImageData(64, 64);
    const rand = seededRandom(0xf00f);
    for (let y = 0; y < 64; y += 1) {
        for (let x = 0; x < 64; x += 1) {
            const d = Math.hypot(x - 31.5, y - 31.5) / 32;
            const a = Math.max(0, 1 - d);
            const alpha = Math.pow(a, 2.2) * 255 + (rand() - 0.5) * 6;
            const i = (y * 64 + x) * 4;
            img.data[i] = 255;
            img.data[i + 1] = 255;
            img.data[i + 2] = 255;
            img.data[i + 3] = Math.round(Math.min(Math.max(alpha, 0), 255));
        }
    }
    ctx.putImageData(img, 0, 0);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
}

/** Astrophoto-style corona: hundreds of noisy radial spikes, dithered. */
export function makeSpikedCorona(seed: number, color: string): THREE.CanvasTexture {
    const size = 512;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d')!;
    const rand = seededRandom(seed);
    const tint = new THREE.Color(color);
    const rgb = `${Math.round(tint.r * 255)}, ${Math.round(tint.g * 255)}, ${Math.round(tint.b * 255)}`;
    const c = size / 2;

    const glow = ctx.createRadialGradient(c, c, 2, c, c, c);
    glow.addColorStop(0, `rgba(${rgb}, 0.9)`);
    glow.addColorStop(0.25, `rgba(${rgb}, 0.28)`);
    glow.addColorStop(0.6, `rgba(${rgb}, 0.07)`);
    glow.addColorStop(1, `rgba(${rgb}, 0)`);
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, size, size);

    ctx.globalCompositeOperation = 'lighter';
    ctx.strokeStyle = `rgba(${rgb}, 0.16)`;
    for (let i = 0; i < 170; i += 1) {
        const angle = rand() * Math.PI * 2;
        const len = c * (0.22 + Math.pow(rand(), 2.2) * 0.72);
        const w = 0.5 + rand() * 1.8;
        ctx.lineWidth = w;
        ctx.globalAlpha = 0.25 + rand() * 0.5;
        ctx.beginPath();
        ctx.moveTo(c + Math.cos(angle) * c * 0.05, c + Math.sin(angle) * c * 0.05);
        ctx.lineTo(c + Math.cos(angle) * len, c + Math.sin(angle) * len);
        ctx.stroke();
    }
    ctx.globalAlpha = 1;

    // Dither pass to break gradient banding.
    const img = ctx.getImageData(0, 0, size, size);
    for (let i = 3; i < img.data.length; i += 4) {
        img.data[i] = Math.min(Math.max(img.data[i] + (rand() - 0.5) * 5, 0), 255);
    }
    ctx.putImageData(img, 0, 0);

    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
}

/** Anamorphic streak with chromatic edges: one horizontal film flare, not
 *  eight perfect spokes. */
export function makeAnamorphicStreak(color: string): THREE.CanvasTexture {
    const w = 512;
    const h = 128;
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d')!;
    const tint = new THREE.Color(color).lerp(new THREE.Color('#ffffff'), 0.5);
    ctx.globalCompositeOperation = 'lighter';
    const layers: [string, number, number][] = [
        [`rgba(120, 160, 255, 0.5)`, w * 0.5, 3.2],
        [
            `rgba(${Math.round(tint.r * 255)}, ${Math.round(tint.g * 255)}, ${Math.round(tint.b * 255)}, 0.85)`,
            w * 0.46,
            2.2,
        ],
        [`rgba(255, 190, 160, 0.4)`, w * 0.4, 1.6],
    ];
    for (const [style, len, thickness] of layers) {
        const grad = ctx.createLinearGradient(w / 2 - len, 0, w / 2 + len, 0);
        grad.addColorStop(0, 'rgba(0,0,0,0)');
        grad.addColorStop(0.5, style);
        grad.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = grad;
        ctx.fillRect(w / 2 - len, h / 2 - thickness, len * 2, thickness * 2);
    }
    const core = ctx.createRadialGradient(w / 2, h / 2, 1, w / 2, h / 2, h / 2);
    core.addColorStop(0, 'rgba(255,255,255,0.9)');
    core.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = core;
    ctx.fillRect(0, 0, w, h);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
}

/** Nebula cloud: fBm-shaped alpha, not a radial blob. */
export function makeNebulaTexture(seed: number, color: string): THREE.CanvasTexture {
    const size = 256;
    const noise = makeNoise3D(seed);
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d')!;
    const img = ctx.createImageData(size, size);
    const tint = new THREE.Color(color);
    const rand = seededRandom(seed ^ 0xbeef);
    for (let y = 0; y < size; y += 1) {
        for (let x = 0; x < size; x += 1) {
            const u = x / size - 0.5;
            const v = y / size - 0.5;
            const d = Math.hypot(u, v) * 2;
            const falloff = Math.max(0, 1 - d * d);
            const cloud = Math.max(0, fbm3(noise, u * 5, v * 5, 0.7, 5) * 0.8 + 0.25);
            const a = Math.pow(cloud * falloff, 1.6);
            const i = (y * size + x) * 4;
            const hueShift = fbm3(noise, u * 3 + 9, v * 3 + 9, 2.1, 3) * 0.3;
            img.data[i] = Math.round(Math.min(tint.r * (1 + hueShift), 1) * 255);
            img.data[i + 1] = Math.round(Math.min(tint.g * (1 - hueShift * 0.3), 1) * 255);
            img.data[i + 2] = Math.round(Math.min(tint.b * (1 + Math.abs(hueShift)), 1) * 255);
            img.data[i + 3] = Math.round(Math.min(Math.max(a * 255 + (rand() - 0.5) * 6, 0), 255));
        }
    }
    ctx.putImageData(img, 0, 0);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
}

/** Lit-windows emissive strip for door stations. */
export function makeWindowStrip(seed: number): THREE.CanvasTexture {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 16;
    const ctx = canvas.getContext('2d')!;
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, 512, 16);
    const rand = seededRandom(seed);
    for (let x = 6; x < 512; x += 10) {
        if (rand() < 0.72) {
            ctx.fillStyle = rand() < 0.85 ? '#ffd9a0' : '#a8d8ff';
            ctx.fillRect(x, 6, 4, 4);
        }
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.wrapS = THREE.RepeatWrapping;
    return texture;
}

/** A planet's ring: one band per file the folder holds, seeded widths and
 *  brightness with dusty gaps between, drawn as concentric annuli so it maps
 *  straight onto a RingGeometry's planar UVs. Dust, not rock: the material a
 *  planet holds (REF-Universe par. 3). */
export function makeRingTexture(seed: number, bandCount: number): THREE.CanvasTexture {
    const size = 512;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d')!;
    const rand = seededRandom(seed);
    const bands = Math.max(1, bandCount);
    // Radial profile over [inner, outer] of the half-size, bands then gaps.
    const inner = 0.56;
    const outer = 0.98;
    const span = outer - inner;
    const weights = Array.from({ length: bands }, () => 0.6 + rand() * 1.2);
    const total = weights.reduce((a, b) => a + b, 0);
    const gapShare = bands > 1 ? 0.22 : 0.1;
    const gap = (span * gapShare) / bands;
    const img = ctx.createImageData(size, size);
    const noise = makeNoise3D(seed ^ 0x9e37);
    let edge = inner;
    const profile: { from: number; to: number; bright: number }[] = [];
    for (let b = 0; b < bands; b += 1) {
        const width = (span * (1 - gapShare) * weights[b]) / total;
        profile.push({ from: edge, to: edge + width, bright: 0.55 + rand() * 0.45 });
        edge += width + gap;
    }
    const half = size / 2;
    for (let y = 0; y < size; y += 1) {
        for (let x = 0; x < size; x += 1) {
            const dx = (x + 0.5 - half) / half;
            const dy = (y + 0.5 - half) / half;
            const r = Math.hypot(dx, dy);
            let alpha = 0;
            for (const band of profile) {
                if (r >= band.from && r <= band.to) {
                    const w = band.to - band.from;
                    const t = (r - band.from) / w;
                    const feather = Math.min(t, 1 - t) * w * 40;
                    const grain = 0.8 + 0.2 * noise(r * 90, dx * 3, dy * 3);
                    alpha = band.bright * Math.min(feather, 1) * grain;
                    break;
                }
            }
            const i = (y * size + x) * 4;
            const tint = 0.9 + 0.1 * noise(r * 40, 0, 0);
            img.data[i] = Math.round(232 * tint);
            img.data[i + 1] = Math.round(218 * tint);
            img.data[i + 2] = Math.round(196 * tint);
            img.data[i + 3] = Math.round(Math.min(Math.max(alpha, 0), 1) * 255);
        }
    }
    ctx.putImageData(img, 0, 0);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
}

// ---------------------------------------------------------- materials

/** GLSL: animated fBm granulation with limb darkening; the sun's surface. */
export function makeSunMaterial(color: string, intensity = 1.25): THREE.ShaderMaterial {
    return new THREE.ShaderMaterial({
        uniforms: {
            uColor: { value: new THREE.Color(color) },
            uTime: { value: 0 },
            uIntensity: { value: intensity },
        },
        vertexShader: /* glsl */ `
            varying vec2 vUv;
            varying vec3 vNormal;
            varying vec3 vView;
            void main() {
                vUv = uv;
                vNormal = normalize(normalMatrix * normal);
                vec4 mv = modelViewMatrix * vec4(position, 1.0);
                vView = normalize(-mv.xyz);
                gl_Position = projectionMatrix * mv;
            }
        `,
        fragmentShader: /* glsl */ `
            uniform vec3 uColor;
            uniform float uTime;
            uniform float uIntensity;
            varying vec2 vUv;
            varying vec3 vNormal;
            varying vec3 vView;

            float hash(vec2 p) {
                return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
            }
            float noise(vec2 p) {
                vec2 i = floor(p);
                vec2 f = fract(p);
                vec2 u = f * f * (3.0 - 2.0 * f);
                return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
                           mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
            }
            float fbm(vec2 p) {
                float v = 0.0;
                float a = 0.5;
                for (int i = 0; i < 5; i++) {
                    v += a * noise(p);
                    p *= 2.03;
                    a *= 0.5;
                }
                return v;
            }
            void main() {
                vec2 p = vUv * vec2(22.0, 11.0);
                float g = fbm(p + uTime * 0.06 + fbm(p - uTime * 0.04));
                g = pow(g, 1.7);
                float spots = smoothstep(0.34, 0.2, fbm(p * 0.5 + 7.31 + uTime * 0.01));
                float limb = pow(max(dot(normalize(vNormal), normalize(vView)), 0.0), 0.6);
                // White-hot core rising toward the disc center.
                float core = pow(limb, 3.0) * (uIntensity - 1.0);
                vec3 hot = mix(uColor, vec3(1.0), 0.55);
                vec3 surface = mix(uColor * 0.45, hot, g);
                surface = mix(surface, uColor * 0.2, spots * 0.85);
                surface = mix(surface, vec3(1.0), clamp(core, 0.0, 0.85));
                surface *= mix(0.22, 1.2, limb);
                gl_FragColor = vec4(surface * uIntensity, 1.0);
            }
        `,
    });
}

/** The planet shader: albedo + Sobel normals + tiled detail normal, lit by
 *  ITS OWN sun (soft terminator), sea glint, fresnel atmosphere in the
 *  body's accent color. This is what makes a world read as a world. */
export function makePlanetMaterial(
    assets: PlanetAssets,
    detailNormal: THREE.Texture,
    sunDir: THREE.Vector3,
    atmosphereColor: string,
): THREE.ShaderMaterial {
    return new THREE.ShaderMaterial({
        uniforms: {
            uMap: { value: assets.map },
            uNormalMap: { value: assets.normalMap },
            uDetailNormal: { value: detailNormal },
            uRoughMap: { value: assets.roughnessMap },
            uSunDir: { value: sunDir.clone().normalize() },
            uAtmColor: { value: new THREE.Color(atmosphereColor) },
            uHasSea: { value: assets.hasSea ? 1 : 0 },
            uDetailRepeat: { value: 9 },
        },
        vertexShader: /* glsl */ `
            varying vec2 vUv;
            varying vec3 vWorldNormal;
            varying vec3 vWorldPos;
            void main() {
                vUv = uv;
                vWorldNormal = normalize(mat3(modelMatrix) * normal);
                vec4 world = modelMatrix * vec4(position, 1.0);
                vWorldPos = world.xyz;
                gl_Position = projectionMatrix * viewMatrix * world;
            }
        `,
        fragmentShader: /* glsl */ `
            uniform sampler2D uMap;
            uniform sampler2D uNormalMap;
            uniform sampler2D uDetailNormal;
            uniform sampler2D uRoughMap;
            uniform vec3 uSunDir;
            uniform vec3 uAtmColor;
            uniform float uHasSea;
            uniform float uDetailRepeat;
            varying vec2 vUv;
            varying vec3 vWorldNormal;
            varying vec3 vWorldPos;

            void main() {
                vec3 albedo = texture2D(uMap, vUv).rgb;
                float rough = texture2D(uRoughMap, vUv).r;

                // Tangent basis on the sphere from the equirect mapping.
                vec3 N = normalize(vWorldNormal);
                vec3 T = normalize(cross(vec3(0.0, 1.0, 0.0), N));
                vec3 B = cross(N, T);
                vec3 nTex = texture2D(uNormalMap, vUv).xyz * 2.0 - 1.0;
                vec3 nDet = texture2D(uDetailNormal, vUv * uDetailRepeat).xyz * 2.0 - 1.0;
                vec3 nBlend = normalize(vec3(nTex.xy + nDet.xy * 0.55, nTex.z));
                N = normalize(T * nBlend.x + B * nBlend.y + N * nBlend.z);

                vec3 L = normalize(uSunDir);
                vec3 V = normalize(cameraPosition - vWorldPos);
                float nl = dot(N, L);
                // Soft terminator: dusk band instead of a hard cut.
                float day = smoothstep(-0.12, 0.25, nl);
                float ambient = 0.055;

                vec3 lit = albedo * (day * 1.25 + ambient);

                // Sea glint: tight specular where the roughness map says water.
                vec3 H = normalize(L + V);
                float spec = pow(max(dot(N, H), 0.0), mix(24.0, 160.0, uHasSea)) *
                    (1.0 - rough) * day;
                lit += vec3(1.0, 0.98, 0.92) * spec * 0.9;

                // Fresnel atmosphere, brightest on the lit limb.
                float fresnel = pow(1.0 - max(dot(normalize(vWorldNormal), V), 0.0), 2.6);
                float sunSide = 0.35 + 0.65 * day;
                lit += uAtmColor * fresnel * sunSide * 0.55;

                gl_FragColor = vec4(lit, 1.0);
            }
        `,
    });
}

/** Shimmering portal membrane for door stations. */
export function makePortalMaterial(color: string): THREE.ShaderMaterial {
    return new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending,
        uniforms: {
            uColor: { value: new THREE.Color(color) },
            uTime: { value: 0 },
        },
        vertexShader: /* glsl */ `
            varying vec2 vUv;
            void main() {
                vUv = uv;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: /* glsl */ `
            uniform vec3 uColor;
            uniform float uTime;
            varying vec2 vUv;
            float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
            float noise(vec2 p) {
                vec2 i = floor(p); vec2 f = fract(p);
                vec2 u = f * f * (3.0 - 2.0 * f);
                return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x),
                           mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
            }
            void main() {
                vec2 c = vUv - 0.5;
                float r = length(c) * 2.0;
                float angle = atan(c.y, c.x);
                float swirl = noise(vec2(angle * 2.0 + uTime * 0.6, r * 4.0 - uTime * 0.9));
                float rim = smoothstep(1.0, 0.72, r);
                float core = smoothstep(0.55, 0.0, r) * 0.5;
                float a = (swirl * 0.55 + 0.25) * rim + core;
                vec3 col = mix(uColor, vec3(1.0), core + swirl * 0.2);
                gl_FragColor = vec4(col, a * 0.85);
            }
        `,
    });
}
