# skincare-rules MCP server

The ingredient-interaction engine, exposed so any MCP client can query it.

**Data:** `data/skincare.db`, compiled by `build_db.py` from the YAML in
`data/`. Read-only. 32 ingredients, 29 interaction rules, 5 contraindication
gates, 74 catalogue products, ingredient names in English, Korean, French,
Japanese and Chinese.

## Running it

```bash
python build_db.py            # once, to compile the database
python mcp_server/server.py   # stdio
```

To see what the tools return without an MCP client:

```bash
python mcp_server/server.py --demo
```

Connection config is in `.mcp.json` at the repo root.

## Tools

| Tool | Reads | What it is for |
|---|---|---|
| `resolve_ingredients(label_text)` | `ingredients`, `ingredient_terms` | Find known actives in a block of label text, in any supported language |
| `lookup_ingredient(name)` | `ingredients` | Everything the table holds about one ingredient |
| `check_interactions(ingredient_ids)` | `interactions` | Which rules fire for a set of ingredients used together |
| `check_contraindications(ids, conditions)` | `contraindications` | Gates that route to a clinician |
| `find_product(name)` | `catalogue`, `catalogue_terms` | Actives for a known product, when no label is available |
| `layering_order()` | `product_forms` | Canonical application order |
| `coverage()` | all | What the server knows, and how much is verified |

Every answer carries the `rule_id` that produced it and whether that rule has
been checked against a source. An ingredient the table does not know returns
`found: false` rather than a guess.

## Why the web app does not route through this

It would be a spawned subprocess sitting between an upload and an answer, and
the engine it would be calling is already in the same process. That is a
failure mode bought for nothing, and the project is graded in part on a
stranger being able to clone the repo and have it running inside ten minutes.

The split is deliberate:

- **the app** calls the engine directly, so the path from a photograph to a
  result is one process
- **the agents** may attach this server as a toolset when they want to look an
  ingredient up mid-task
- **anyone else** can point their own client at it

The last of those is the point. The rules table is the part of this project
worth reusing, and an MCP server is how it becomes reusable by something that
is not this app — you can ask Claude Desktop whether your retinol clashes with
your acne wash without any of the rest of this running.

## What it will not do

No writes, no network, no model calls. It answers from the table or says it
cannot. Rules not yet checked against a primary source are marked `verified:
false` in every response that depends on them — see the warning at the top of
`data/interactions.yaml`.
