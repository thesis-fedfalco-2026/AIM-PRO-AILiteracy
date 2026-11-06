# Schema compilation probes

After attempts 04 and 05 were rejected by the grammar compiler, the owner
authorized request `scn01-schema-probes-01`, manifest
`8f1d49267920a148a1dffdd20dfba82c8f4685999cae665336716fec84706337`: at most eleven
single-shot requests to Anthropic direct `claude-sonnet-4-6` with `max_tokens: 1`,
no retry and a USD 0.50 budget ([authorization](model-transmission-authorization.json)).
Each request carried one [candidate schema](candidates.json) and a one-line
synthetic prompt. No course content, sources, assessment or prior output was sent,
and no authoring database was opened.

## Results

All eleven probes were sent and none stopped the run
([results](probe-results.json), [summary](run-summary.json)). The estimated
cost of the five accepted probes is USD 0.028; the six rejected probes returned
no usage and their cost is unknown.

| ID | Variant | Inlined bytes | Outcome |
|---|---|---|---|
| C01 | legacy schema of attempts 01–03 (positive control) | 2,348 | accepted |
| C02 | compact schema of attempt 05 (negative control) | 5,530 | rejected |
| C03 | C02 without descriptions | 5,530 | rejected |
| C04 | C02 without the transcript-part union | 5,141 | rejected |
| C05 | C02 without citation arrays | 3,615 | rejected |
| C06 | units + explanations | 1,968 | accepted |
| C07 | units + comparisons | 2,375 | accepted |
| C08 | units + peers | 2,710 | accepted |
| C09 | units + transcripts (with union) | 2,554 | accepted |
| C10 | units + explanations, comparisons, peers | 4,335 | rejected |
| C11 | C02 without union and citations | 3,226 | rejected |

"Inlined bytes" expands `$ref`s and drops descriptions/titles. It is a local
proxy, not the provider's metric.

## Interpretation

Both controls behaved as expected, so the results are interpretable. Every asset
group compiles on its own, including the transcript union. Removing descriptions,
the union or citations does not make the full schema compile. Rejection follows
the combined size: the largest accepted candidate is 2,710 proxy bytes and the
smallest rejected one 3,226. The full structured Teacher contract therefore
cannot be sent as a single constrained schema. No single construct is the cause.

Limits: one observation per schema on 6 November 2026. The provider's internal
limit is undocumented and may change. The byte proxy only orders these
candidates. Any next Teacher run needs its own packet and authorization;
Chat 06 remains blocked.
