```javascript
const generateReferralCode = () => {
  return Math.random().toString(36).substring(2, 8).toUpperCase();
};

const calculateEarnings = (duration, ratePerInterval, interval) => {
  const segments = Math.floor(duration / interval);
  return segments * ratePerInterval;
};

const formatDate = (date) => {
  return date.toISOString().split('T')[0];
};

module.exports = {
  generateReferralCode,
  calculateEarnings,
  formatDate
};
```
