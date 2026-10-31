import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const sourceDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src');

function moduleBindings(source) {
  const bindings = new Set();
  for (const match of source.matchAll(/import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]/g)) {
    const clause = match[1].trim();
    const defaultImport = clause.match(/^([A-Za-z_$][\w$]*)/);
    if (defaultImport) bindings.add(defaultImport[1]);
    const namedImports = clause.match(/\{([^}]+)\}/)?.[1] || '';
    for (const item of namedImports.split(',')) {
      const name = item.trim().split(/\s+as\s+/).at(-1);
      if (name) bindings.add(name);
    }
  }
  for (const match of source.matchAll(/\b(?:function|class|const|let)\s+([A-Za-z_$][\w$]*)/g)) bindings.add(match[1]);
  for (const match of source.matchAll(/\bicon\s*:\s*([A-Z][\w$]*)/g)) bindings.add(match[1]);
  return bindings;
}

test('dashboard JSX component names are imported or declared in their module', async () => {
  for (const filename of ['App.jsx', 'DashboardPages.jsx', 'DashboardComponents.jsx', 'ApiDocumentation.jsx']) {
    const source = await readFile(path.join(sourceDir, filename), 'utf8');
    const bindings = moduleBindings(source);
    const usedComponents = new Set([...source.matchAll(/<([A-Z][A-Za-z0-9_$]*)\b/g)].map((match) => match[1]));
    const unresolved = [...usedComponents].filter((name) => !bindings.has(name));
    assert.deepEqual(unresolved, [], `${filename} has unresolved JSX names: ${unresolved.join(', ')}`);
  }
});
