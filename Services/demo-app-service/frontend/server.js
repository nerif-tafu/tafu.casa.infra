const express = require('express');
const app = express();
const port = 9000;

app.get('/', (req, res) => {
  res.send('Frontend Server Running');
});

app.listen(port, () => {
  console.log(`Frontend server listening at http://localhost:${port}`);
}); 