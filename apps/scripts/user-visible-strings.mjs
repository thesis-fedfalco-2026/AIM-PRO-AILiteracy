// Find user-visible text written directly in components instead of a string catalogue.
//
// A finding is JSX text with a letter, a string literal used as a JSX child, or
// a string literal given to an attribute people read or hear (aria-label, title,
// alt, placeholder, label). Punctuation, class names, ids and other attributes
// are allowed. Tests are not scanned.

import { readdir, readFile } from 'node:fs/promises';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

import ts from 'typescript';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const SOURCE_DIRS = ['packages', 'studio'];
const VISIBLE_ATTRIBUTES = new Set([
  'alt', 'aria-description', 'aria-label', 'aria-placeholder', 'aria-roledescription', 'aria-valuetext',
  'label', 'placeholder', 'title',
]);
const LETTER = /\p{L}/u;

/**
 * Literal texts an expression can evaluate to, through conditionals and `&&`, `||`, `??`.
 * @param {ts.Expression} node
 * @returns {string[]}
 */
function literalTexts(node) {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return [node.text];
  if (ts.isTemplateExpression(node)) {
    return [node.head.text + node.templateSpans.map((span) => '${…}' + span.literal.text).join('')];
  }
  if (ts.isParenthesizedExpression(node)) return literalTexts(node.expression);
  if (ts.isConditionalExpression(node)) return [...literalTexts(node.whenTrue), ...literalTexts(node.whenFalse)];
  if (ts.isBinaryExpression(node) && [ts.SyntaxKind.AmpersandAmpersandToken, ts.SyntaxKind.BarBarToken,
    ts.SyntaxKind.QuestionQuestionToken].includes(node.operatorToken.kind)) return literalTexts(node.right);
  return [];
}

/** @typedef {{ file: string, line: number, text: string }} Finding */

/**
 * Findings of one TSX source, in source order.
 * @param {string} sourceText
 * @param {string} fileName
 * @returns {Finding[]}
 */
export function hardCodedStrings(sourceText, fileName) {
  const source = ts.createSourceFile(fileName, sourceText, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  /** @type {Finding[]} */
  const findings = [];
  /** @param {ts.Node} node @param {string} text */
  const report = (node, text) => {
    if (!LETTER.test(text)) return;
    const line = source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;
    findings.push({ file: fileName, line, text: text.trim().replace(/\s+/g, ' ') });
  };
  /** @param {ts.Node} node */
  const visit = (node) => {
    if (ts.isJsxText(node)) {
      report(node, node.text);
    } else if (ts.isJsxExpression(node) && node.expression && !ts.isJsxAttribute(node.parent)) {
      for (const text of literalTexts(node.expression)) report(node, text);
    } else if (ts.isJsxAttribute(node) && node.initializer && VISIBLE_ATTRIBUTES.has(node.name.getText(source))) {
      const value = ts.isJsxExpression(node.initializer) ? node.initializer.expression : node.initializer;
      for (const text of value ? literalTexts(value) : []) report(node, text);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return findings;
}

/**
 * @param {string} directory
 * @returns {AsyncGenerator<string>}
 */
async function* tsxFiles(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (entry.name === 'node_modules' || entry.name === 'test' || entry.name === 'dist') continue;
    const path = join(directory, entry.name);
    if (entry.isDirectory()) yield* tsxFiles(path);
    else if (entry.name.endsWith('.tsx')) yield path;
  }
}

/** Component files of the workspace, relative to apps/. */
export async function componentFiles(root = ROOT) {
  /** @type {string[]} */
  const files = [];
  for (const directory of SOURCE_DIRS) {
    for await (const path of tsxFiles(join(root, directory))) files.push(relative(root, path));
  }
  return files.sort();
}

export async function scanWorkspace(root = ROOT) {
  /** @type {Finding[]} */
  const findings = [];
  for (const file of await componentFiles(root)) {
    findings.push(...hardCodedStrings(await readFile(join(root, file), 'utf8'), file));
  }
  return findings;
}
