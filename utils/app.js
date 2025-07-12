```javascript
const express = require('express');
const connectDB = require('./config/database');
const securityMiddleware = require('./middleware/security');
const { apiLimiter } = require('./middleware/rateLimiter');
const routes = require('./routes');
const errorHandler = require('./middleware/errorHandler');
const logger = require('./utils/logger');

const app = express();

// Connect to database
connectDB();

// Security middleware
securityMiddleware(app);

// Rate limiting
app.use('/api/', apiLimiter);

// Routes
app.use('/api', routes);

// Error handling
app.use(errorHandler);

// Handle 404
app.use((req, res) => {
  res.status(404).json({ error: 'Route not found' });
});

module.exports = app;
```
