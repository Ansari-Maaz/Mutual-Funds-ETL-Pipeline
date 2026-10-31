export function escapeCsvCell(value) {
  let text = String(value ?? '');
  // Spreadsheet programs execute cells that begin with formula operators.
  if (/^[\s\u0000-\u001f]*[=+@-]/.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

export function rowsToCsv(rows, columns) {
  return [columns.join(','), ...rows.map((row) => columns.map((key) => escapeCsvCell(row[key])).join(','))].join('\n');
}
