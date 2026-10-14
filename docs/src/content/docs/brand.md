---
title: Visual identity
id: DOC-REF-BRAND-001
type: Reference
status: Active
updated: "2026-09-13"
description: The Vodafone Portugal Digital identity and the application-owned styling sources.
---

Playbook Studio wears the Vodafone Portugal Digital identity with a full-width workspace and 24px desktop gutters for its map, navigation and document readers: the lockup in the header, the brand's red as the primary and the ambient field's colour over neutral greys, the brand face for text and JetBrains Mono for the lockup's second line.

## Application sources

| Surface | Source |
| --- | --- |
| Application and graph tokens, spacing, motion | `studio-frontend/src/index.css` |
| Header, wordmark and navigation | `studio-frontend/src/views/templates/MainLayout.tsx` |
| Continuous side fields and fading particles | `studio-frontend/src/views/atoms/AmbientField.tsx` |
| Typography utilities | `studio-frontend/tailwind.config.js` |
| Browser mark | `studio-frontend/public/logo-mark.svg` |

Light/Dark is the existing persisted reading preference. Decorative motion runs in both appearances, pauses on hidden pages and stops for reduced motion. Cards and readers are opaque working surfaces. Printed pages omit ambient decoration and navigation.

Graph labels and edges use application tokens. Galaxy and domain colours express the map's categories; the three-dimensional universe owns its scene lighting and materials. Corpus exports remain Markdown authored by their owning galaxy.
