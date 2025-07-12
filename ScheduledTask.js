```javascript
const { OwnerEarnings, User } = require('../models');
const logger = require('../utils/logger');

const resetDailyEarnings = async () => {
  try {
    await OwnerEarnings.updateOne(
      {},
      { $set: { todayEarnings: 0, lastReset: new Date() } }
    );
    logger.info('Daily earnings reset completed');
  } catch (error) {
    logger.error('Error resetting daily earnings:', error);
  }
};

const cleanupExpiredTokens = async () => {
  try {
    await User.deleteMany({
      isVerified: false,
      createdAt: { $lt: new Date(Date.now() - 24 * 60 * 60 * 1000) }
    });
    logger.info('Expired tokens cleanup completed');
  } catch (error) {
    logger.error('Error cleaning up expired tokens:', error);
  }
};

const startScheduledTasks = () => {
  // Run cleanup tasks every hour
  setInterval(cleanupExpiredTokens, 60 * 60 * 1000);
  
  // Reset daily earnings at midnight
  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);
  tomorrow.setHours(0, 0, 0, 0);
  
  const msUntilMidnight = tomorrow.getTime() - now.getTime();
  setTimeout(() => {
    resetDailyEarnings();
    setInterval(resetDailyEarnings, 24 * 60 * 60 * 1000);
  }, msUntilMidnight);
};

module.exports = { startScheduledTasks };
```
