```javascript
const express = require('express');
const authRoutes = require('./auth');
const userRoutes = require('./user');
const videoRoutes = require('./video');
const paymentRoutes = require('./payment');
const adminRoutes = require('./admin');

const router = express.Router();

router.use('/auth', authRoutes);
router.use('/user', userRoutes);
router.use('/videos', videoRoutes);
router.use('/payments', paymentRoutes);
router.use('/admin', adminRoutes);

module.exports = router;
```
