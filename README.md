# Hotel Bookings Dashboard - Vega-Lite

A static, browser-rendered rebuild of a Tableau dashboard analysing the
public hotel-bookings dataset, using **Vega-Lite** specifications loaded
into a single HTML page. No backend, no server, no Python at runtime.

---

## What it shows

1. **Market segment quadrant matrix** - bubble chart plotting average
   daily rate against cancellation rate for each `hotel x market_segment`,
   sized by booking volume. Dashed reference lines split the chart into
   four quadrants.
2. **Average daily rate by month** - City vs Resort hotel, with a
   horizontal target reference line. Months whose avg ADR is at or above
   the target are labelled with month name + ADR. Both update live when
   the user changes the Target ADR input.
3. **Cancellation rate by advance booking window** - grouped bars across
   five lead-time bands (`0-90`, `90-180`, `180-270`, `270-365`,
   `365+ days`) with the cancellation rate labelled on each bar.

---

## Project layout

```
hotel-bookings-dashboard/
├── index.html            # Page layout + vega-embed + input wiring
├── specs/
│   ├── bubble.vl.json    # 5-layer scatter with reference lines
│   ├── line.vl.json      # Reactive line chart, target ADR param
│   └── bars.vl.json      # Grouped bars, faceted by lead-time band
├── data/
│   ├── hotel_bookings.csv      # Raw data (gitignored)
│   ├── segment_matrix.csv      # Bubble chart source
│   ├── adr_by_month.csv        # Line chart source
│   └── cancel_by_lead.csv      # Bar chart source
├── data_prep.py          # One-off Python script: raw CSV -> 3 aggregates
├── render.yaml           # Render Static Site definition
├── .gitignore
└── README.md
```

---

## Running locally

Vega-Lite specs fetch CSV files via relative URLs, so you need to serve
the directory over HTTP - opening `index.html` directly with `file://`
will fail with CORS errors.

```bash
# From the repo root
python3 -m http.server 8000

# Then open http://localhost:8000 in a browser
```

That's it - no install step, no virtual environment, no Python
dependencies at runtime. Python is only needed if you want to regenerate
the aggregate CSVs from the raw data:

```bash
pip install pandas
python data_prep.py
```

---

## Deploying to Render

This is a **Static Site** on Render, not a Web Service. Static sites are
free, serve from a CDN, never sleep, and have no cold starts.

The repo includes `render.yaml`, so deployment is one click:

1. Push to GitHub.
2. Render -> New -> Blueprint -> connect this repo.
3. Render reads `render.yaml`, creates a Static Site, publishes the repo
   root, done. First deploy takes ~30 seconds.

If you'd rather configure manually in the Render UI:

- New -> **Static Site**
- Branch: `main`
- Build command: *(leave empty)*
- Publish directory: `.`

---

## Understanding the Vega-Lite specs

Each chart is a JSON file with the same skeleton:

```json
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data":      { ... },        // where the rows come from
  "transform": [ ... ],        // optional: filter, aggregate, calculate
  "mark":      { ... },        // the geometric shape (or `layer` for many)
  "encoding":  { ... }         // field -> visual channel mapping
}
```

### Concept 1 - `mark` and `encoding`

The mark is the geometric shape: `circle`, `line`, `bar`, `rule`, `text`,
`area`, `point`. Encodings tell Vega-Lite how data fields map to visual
channels (`x`, `y`, `color`, `size`, `text`, `tooltip`, `xOffset`,
`column`, `row`).

You don't tell Vega-Lite *how* to draw - you tell it *what* the channels
mean. It picks the axis ranges, the legend, the layout. You override only
when needed (e.g. fixing a colour scale).

### Concept 2 - `layer` for stacking marks on shared scales

The bubble chart uses 5 layers on the same x/y axes:

1. The bubbles themselves (`circle` mark)
2. Segment-name labels next to each bubble (`text` mark)
3. Vertical dashed reference line at x=30 (`rule` mark, inline data)
4. Horizontal dashed reference line at the mean ADR (`rule` mark, computed
   via an `aggregate` transform)
5. Four quadrant annotation labels in the corners (`text` mark, inline data)

Each layer can have its own `data`, `transform`, `mark`, and `encoding`.
This is how you build dense, annotated charts without procedural code.

### Concept 3 - `params` for live interactivity

The line chart declares a parameter:

```json
"params": [
  {"name": "targetADR", "value": 115}
]
```

Three things in the spec depend on `targetADR`:

- The conditional label layer:
  `"transform": [{"filter": "datum.avg_adr >= targetADR"}]`
- The horizontal target rule:
  `"y": {"datum": {"expr": "targetADR"}}`
- The target's text label:
  `"text": {"value": {"expr": "'Target_' + targetADR + 'ADR'"}}`

When the param changes, Vega-Lite re-evaluates the dependency graph and
re-renders **only** those three pieces. Everything else stays untouched.

### Concept 4 - external input wiring

Vega-Lite can auto-generate an HTML input via `bind: {input: "number"}`
inside the param declaration. We deliberately *don't* do that, so the
input lives in our own HTML and we can style it however we want.

The bridge is two lines of JavaScript in `index.html`:

```js
const { view } = await vegaEmbed('#line', 'specs/line.vl.json');
input.addEventListener('input', e => {
  view.signal('targetADR', Number(e.target.value)).runAsync();
});
```

`view.signal(name, value).runAsync()` updates the param and triggers the
minimal re-render. That's the entire reactivity mechanism.

### Concept 5 - top-level `encoding` is inherited by layers

The line chart sets `x` and `color` at the top level. All five layers
inherit those, so the line, the points, and the labels share the same
month-axis and the same hotel-colour scheme without repeating the
encoding block.

The two layers that *don't* want to inherit (the target rule and its
label, which span the whole chart and aren't per-hotel) override the
inheritance with `"x": null, "color": null` and supply their own
one-row dataset with `"data": {"values": [{}]}`. This is a Vega-Lite
gotcha worth knowing - inherited encodings will silently produce one
mark per data row if you don't explicitly opt out.

### Concept 6 - `xOffset` for grouped bars

The bar chart uses `x: lead_band` for the outer grouping and
`xOffset: hotel` for the inner grouping. Vega-Lite produces grouped
bars (City and Resort side by side under each band label) automatically.
No manual width or position calculations.

---

## Tableau -> Vega-Lite translation table

| Tableau concept                   | Vega-Lite equivalent                                              |
|-----------------------------------|-------------------------------------------------------------------|
| Calculated field `Cancellation Rate %` | Pre-computed in `data_prep.py` (could also use `transform: aggregate`) |
| Calculated field `Lead time band` | Pre-computed in `data_prep.py` via `pd.cut`                       |
| Parameter `Target_115ADR`         | `params: [{name: "targetADR", value: 115}]`                       |
| Calculated field `Above Selected target` | `transform: [{filter: "datum.avg_adr >= targetADR"}]`         |
| Reference line at x=30            | `rule` mark layer with inline data `[{x: 30}]`                    |
| Reference line at AVG(ADR)        | `rule` mark layer with `aggregate` transform                      |
| Quadrant annotation text          | `text` mark layer with 4-row inline data                          |
| Dashboard layout                  | HTML CSS grid (could also use Vega-Lite's `hconcat`/`vconcat`)    |
| Hover tooltip                     | `tooltip` channel in the encoding                                 |
| Click-to-filter dashboard action  | (Not implemented in v1) `params` with `select: {type: "point"}`   |

---

## Why split each chart into its own JSON file?

Two reasons:

1. **Readability.** Each spec stands alone and can be opened, validated,
   and reasoned about in isolation. The schema URL at the top means any
   editor with JSON Schema support gives you autocomplete and inline
   error checking.
2. **Independent rendering.** `vega-embed` loads each spec into its own
   `<div>`. Tooltips, signals, and selections in one chart don't leak
   into another unless we explicitly wire them.

The alternative is a single Vega-Lite spec using `hconcat`/`vconcat` to
compose all three charts. That's more idiomatic when charts share data
or when you want a global selection (e.g. brushing in one chart filters
the others). For our use case - three independent views with one
parameter - separate files are simpler and clearer.

---

## Things deliberately left out of v1

- **Cross-chart filtering.** In the original Tableau, clicking a bubble
  filters the other charts by that segment / hotel. Doable in Vega-Lite
  via `params: [{name: "sel", select: {type: "point", fields: ["hotel"]}}]`
  and referencing `sel` in filters on other specs. Adds complexity; left
  out for v1.
- **Year filter.** Data spans 2015-2017; v1 aggregates all years.
- **Mobile layout.** The CSS grid uses fixed minimum widths; on phones
  the right column wraps below the left, which is acceptable but not
  optimised.
