function notFound(_req, res) {
  res.status(404).json({ error: { code: 'NOT_FOUND', message: 'Route not found' } });
}

function errorHandler(err, _req, res, _next) {
  const status = err.statusCode || err.status || 500;
  const code = err.code || (status >= 500 ? 'INTERNAL_ERROR' : 'REQUEST_ERROR');
  if (status >= 500) console.error(JSON.stringify({ level: 'error', code, message: err.message }));
  res.status(status).json({ error: { code, message: status >= 500 ? 'The request could not be completed' : err.message } });
}

module.exports = { notFound, errorHandler };
