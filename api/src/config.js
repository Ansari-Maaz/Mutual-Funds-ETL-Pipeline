const path = require('node:path');

const projectRoot = path.resolve(__dirname, '../..');
function postgresUrl(value) {
  return (value || 'postgresql://mfetl:mfetl@localhost:5433/mfetl')
    .replace(/^postgresql\+psycopg:\/\//, 'postgresql://');
}

module.exports = {
  projectRoot,
  port: Number(process.env.PORT || 3001),
  databaseUrl: postgresUrl(process.env.DATABASE_URL),
  pythonExecutable: process.env.PYTHON_EXECUTABLE
    ? (path.isAbsolute(process.env.PYTHON_EXECUTABLE) || !process.env.PYTHON_EXECUTABLE.includes('/')
      ? process.env.PYTHON_EXECUTABLE
      : path.resolve(projectRoot, process.env.PYTHON_EXECUTABLE))
    : path.join(projectRoot, '.venv/bin/python'),
  etlTimeoutMs: Number(process.env.ETL_TIMEOUT_MS || 900000),
  adminApiKey: process.env.ADMIN_API_KEY || '',
  frontendOrigin: process.env.FRONTEND_ORIGIN || 'http://localhost:5173',
};
