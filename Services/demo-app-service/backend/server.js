const express = require('express');
const app = express();
const port = 9001;

app.get('/api/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.get('/api/test', (req, res) => {
  res.json({ message: 'Backend API is working' });
});

app.listen(port, () => {
  console.log(`Backend API server listening at http://localhost:${port}`);
}); 