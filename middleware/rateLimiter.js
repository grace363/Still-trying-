```javascript
const rateLimit = require('express-rate-limit');

const createLimiter = (windowMs, max, message) => {
  return rateLimit({
    windowMs,
    max,
    message: { error: message }
  });
};

const apiLimiter = createLimiter(
  15 * 60 * 1000, // 15 minutes
  100, // 100 requests
  'Too many requests from this IP, please try again later.'
);

const authLimiter = createLimiter(
  15 * 60 * 1000, // 15 minutes
  5, // 5 requests
  'Too many authentication attempts from this IP, please try again later.'
);

module.exports = { apiLimiter, authLimiter };
```
