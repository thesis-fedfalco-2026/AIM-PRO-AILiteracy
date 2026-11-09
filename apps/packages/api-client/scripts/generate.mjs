// Generate, or check, the typed Authoring API client from the OpenAPI snapshot.
//
//   node scripts/generate.mjs            rewrite src/generated/authoring.ts for review
//   node scripts/generate.mjs --check    exit 1 when the client differs from the snapshot
//
// --schema and --output select other files (used by the tests).

import { readFile, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';

import openapiTS, { astToString } from 'openapi-typescript';

export const SNAPSHOT = new URL('../../../../services/openapi/authoring.json', import.meta.url);
export const OUTPUT = new URL('../src/generated/authoring.ts', import.meta.url);

const HEADER = `// Generated from services/openapi/authoring.json by
// apps/packages/api-client/scripts/generate.mjs. Do not edit; run
// \`npm run generate:client\` in apps/ after the snapshot changes.

`;

/** @typedef {string | URL} Location */

/**
 * The client source for a snapshot: the same snapshot always gives the same text.
 * @param {Location} [snapshot]
 */
export async function render(snapshot = SNAPSHOT) {
  const schema = JSON.parse(await readFile(snapshot, 'utf8'));
  return HEADER + astToString(await openapiTS(schema, { alphabetize: true }));
}

/**
 * True when the client at `output` is exactly the one `snapshot` generates.
 * @param {Location} [snapshot]
 * @param {Location} [output]
 */
export async function check(snapshot = SNAPSHOT, output = OUTPUT) {
  let current;
  try {
    current = await readFile(output, 'utf8');
  } catch (error) {
    if (/** @type {NodeJS.ErrnoException} */ (error).code === 'ENOENT') return false;
    throw error;
  }
  return current === await render(snapshot);
}

/**
 * @param {Location} [snapshot]
 * @param {Location} [output]
 */
export async function write(snapshot = SNAPSHOT, output = OUTPUT) {
  await writeFile(output, await render(snapshot), 'utf8');
}

async function main() {
  const { values } = parseArgs({
    options: { check: { type: 'boolean' }, schema: { type: 'string' }, output: { type: 'string' } },
  });
  const snapshot = values.schema ?? SNAPSHOT;
  const output = values.output ?? OUTPUT;
  if (!values.check) {
    await write(snapshot, output);
  } else if (!await check(snapshot, output)) {
    process.stderr.write('The generated API client differs from the OpenAPI snapshot; '
      + 'run `npm run generate:client` in apps/ and review the result.\n');
    process.exitCode = 1;
  }
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) {
  await main();
}
