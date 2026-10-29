const express = require('express');
const path = require('node:path');

const router = express.Router();
const specPath = path.resolve(__dirname, '../../openapi.json');

router.get('/openapi.json', (_req, res) => res.sendFile(specPath));

router.get('/docs', (_req, res) => {
  // Scalar is loaded from its public CDN. Keep its required origins scoped to
  // this documentation page; the rest of the API retains Helmet's defaults.
  res.setHeader('Content-Security-Policy', [
    "default-src 'self'",
    "script-src 'self' https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
    "font-src 'self' data: https://cdn.jsdelivr.net",
    "img-src 'self' data: https:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
  ].join('; '));
  res.type('html').send(`<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="FundFlow REST API reference">
    <title>FundFlow API Reference</title>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
  </head>
  <body>
    <scalar-api-reference spec-url="/api/openapi.json"></scalar-api-reference>
  </body>
</html>`);
});

module.exports = router;
