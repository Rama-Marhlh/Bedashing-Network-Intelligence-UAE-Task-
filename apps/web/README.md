# Bedashing web application

The Phase 2 Next.js dashboard is fully static at runtime: it does not require FastAPI, an
LLM, or an external API key. Its analytical inputs are created only by running
`npm run sync:data` from the repository root.

The default inline MapLibre style uses CARTO Light raster tiles with OpenStreetMap data.
Keeping the style inline means analytical layers still render over a neutral background if
tiles fail. Override it with a compatible public MapLibre style URL through
`NEXT_PUBLIC_MAP_STYLE_URL`. This variable is public by design and must never contain a
private token.

Run the dashboard from the repository root:

```powershell
npm run dev
```

Then open `http://localhost:3000`.
