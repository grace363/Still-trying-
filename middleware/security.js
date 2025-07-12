```javascript
const helmet = require('helmet');
const cors = require('cors');

const securityMiddleware = (app) => {
  app.use(helmet());
  app.use(cors());
  app.use(express.json({ limit: '10mb' }));
  app.use(express.urlencoded({ extended: true, limit: '10mb' }));
};

module.exports = securityMiddleware;
```
