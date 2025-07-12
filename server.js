```javascript
require('dotenv').config();
const app = require('./src/app');
const { startScheduledTasks } = require('./src/tasks/scheduledTasks');
const logger = require('./src/utils/logger');

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
  logger.info(`Server running on port ${PORT}`);
  startScheduledTasks();
});
```
