const express = require('express');
const mongoose = require('mongoose');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const cors = require('cors');
const cron = require('node-cron');

const app = express();
app.use(cors());
app.use(express.json());

// MongoDB Connection
mongoose.connect('mongodb://localhost:27017/watchearn', {
  useNewUrlParser: true,
  useUnifiedTopology: true
});

// User Schema
const userSchema = new mongoose.Schema({
  username: { type: String, required: true, unique: true },
  email: { type: String, required: true, unique: true },
  password: { type: String, required: true },
  coins: { type: Number, default: 0 },
  totalWatchTime: { type: Number, default: 0 }, // in minutes
  level: { type: Number, default: 1 },
  referralCode: { type: String, unique: true },
  referredBy: { type: String, default: null },
  referralEarnings: { type: Number, default: 0 },
  premiumUntil: { type: Date, default: null },
  lastActive: { type: Date, default: Date.now },
  isActive: { type: Boolean, default: true },
  deviceInfo: {
    type: { type: String }, // mobile, tablet, desktop
    os: String,
    browser: String,
    country: String
  },
  adPreferences: {
    categories: [String],
    blockedCategories: [String]
  },
  createdAt: { type: Date, default: Date.now }
});

// Content Schema
const contentSchema = new mongoose.Schema({
  title: { type: String, required: true },
  description: String,
  videoUrl: String,
  thumbnailUrl: String,
  duration: { type: Number, required: true }, // in minutes
  category: { type: String, required: true },
  tags: [String],
  coinReward: { type: Number, required: true },
  minWatchTime: { type: Number, default: 0.5 }, // minimum watch time to earn
  ageRating: { type: String, default: 'G' },
  language: { type: String, default: 'en' },
  isActive: { type: Boolean, default: true },
  views: { type: Number, default: 0 },
  likes: { type: Number, default: 0 },
  createdAt: { type: Date, default: Date.now }
});

// Watch Session Schema
const watchSessionSchema = new mongoose.Schema({
  userId: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  contentId: { type: mongoose.Schema.Types.ObjectId, ref: 'Content', required: true },
  startTime: { type: Date, required: true },
  endTime: Date,
  watchDuration: { type: Number, default: 0 }, // in minutes
  coinsEarned: { type: Number, default: 0 },
  adsShown: { type: Number, default: 0 },
  adClicks: { type: Number, default: 0 },
  ownerRevenue: { type: Number, default: 0 }, // your earnings from this session
  completed: { type: Boolean, default: false },
  quality: { type: String, default: '720p' },
  deviceType: String,
  ipAddress: String,
  createdAt: { type: Date, default: Date.now }
});

// Ad Schema
const adSchema = new mongoose.Schema({
  title: { type: String, required: true },
  description: String,
  imageUrl: String,
  videoUrl: String,
  clickUrl: { type: String, required: true },
  category: { type: String, required: true },
  targetAudience: {
    ageRange: [Number],
    interests: [String],
    countries: [String]
  },
  budget: { type: Number, required: true },
  costPerView: { type: Number, required: true },
  costPerClick: { type: Number, required: true },
  maxDailyBudget: { type: Number, required: true },
  isActive: { type: Boolean, default: true },
  views: { type: Number, default: 0 },
  clicks: { type: Number, default: 0 },
  conversions: { type: Number, default: 0 },
  createdAt: { type: Date, default: Date.now }
});

// Revenue Schema (Your earnings tracking)
const revenueSchema = new mongoose.Schema({
  date: { type: Date, required: true },
  adRevenue: { type: Number, default: 0 },
  premiumRevenue: { type: Number, default: 0 },
  sponsorshipRevenue: { type: Number, default: 0 },
  totalActiveUsers: { type: Number, default: 0 },
  totalWatchTime: { type: Number, default: 0 },
  totalAdViews: { type: Number, default: 0 },
  totalAdClicks: { type: Number, default: 0 },
  averageSessionDuration: { type: Number, default: 0 },
  retentionRate: { type: Number, default: 0 },
  createdAt: { type: Date, default: Date.now }
});

// Withdrawal Schema
const withdrawalSchema = new mongoose.Schema({
  userId: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  amount: { type: Number, required: true },
  method: { type: String, required: true }, // paypal, bank, crypto
  details: {
    paypalEmail: String,
    bankAccount: String,
    cryptoWallet: String
  },
  status: { type: String, default: 'pending' }, // pending, approved, rejected, completed
  processedAt: Date,
  createdAt: { type: Date, default: Date.now }
});

// Create Models
const User = mongoose.model('User', userSchema);
const Content = mongoose.model('Content', contentSchema);
const WatchSession = mongoose.model('WatchSession', watchSessionSchema);
const Ad = mongoose.model('Ad', adSchema);
const Revenue = mongoose.model('Revenue', revenueSchema);
const Withdrawal = mongoose.model('Withdrawal', withdrawalSchema);

// Middleware for authentication
const authenticateToken = (req, res, next) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];
  
  if (!token) {
    return res.status(401).json({ error: 'Access token required' });
  }
  
  jwt.verify(token, process.env.JWT_SECRET || 'your-secret-key', (err, user) => {
    if (err) return res.status(403).json({ error: 'Invalid token' });
    req.user = user;
    next();
  });
};

// Generate referral code
const generateReferralCode = () => {
  return Math.random().toString(36).substring(2, 8).toUpperCase();
};

// AUTHENTICATION ENDPOINTS

// Register
app.post('/api/register', async (req, res) => {
  try {
    const { username, email, password, referralCode } = req.body;
    
    // Check if user exists
    const existingUser = await User.findOne({ 
      $or: [{ email }, { username }] 
    });
    
    if (existingUser) {
      return res.status(400).json({ error: 'User already exists' });
    }
    
    // Hash password
    const hashedPassword = await bcrypt.hash(password, 10);
    
    // Create user
    const user = new User({
      username,
      email,
      password: hashedPassword,
      referralCode: generateReferralCode(),
      referredBy: referralCode || null,
      coins: referralCode ? 100 : 50 // Bonus for referrals
    });
    
    await user.save();
    
    // Reward referrer
    if (referralCode) {
      await User.findOneAndUpdate(
        { referralCode },
        { $inc: { coins: 50, referralEarnings: 50 } }
      );
    }
    
    // Generate JWT
    const token = jwt.sign(
      { userId: user._id },
      process.env.JWT_SECRET || 'your-secret-key',
      { expiresIn: '30d' }
    );
    
    res.json({
      message: 'User registered successfully',
      token,
      user: {
        id: user._id,
        username: user.username,
        email: user.email,
        coins: user.coins,
        referralCode: user.referralCode
      }
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Login
app.post('/api/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    
    const user = await User.findOne({ email });
    if (!user) {
      return res.status(400).json({ error: 'Invalid credentials' });
    }
    
    const validPassword = await bcrypt.compare(password, user.password);
    if (!validPassword) {
      return res.status(400).json({ error: 'Invalid credentials' });
    }
    
    // Update last active
    user.lastActive = new Date();
    await user.save();
    
    const token = jwt.sign(
      { userId: user._id },
      process.env.JWT_SECRET || 'your-secret-key',
      { expiresIn: '30d' }
    );
    
    res.json({
      message: 'Login successful',
      token,
      user: {
        id: user._id,
        username: user.username,
        email: user.email,
        coins: user.coins,
        level: user.level,
        totalWatchTime: user.totalWatchTime,
        referralCode: user.referralCode
      }
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// CONTENT ENDPOINTS

// Get content feed
app.get('/api/content', authenticateToken, async (req, res) => {
  try {
    const { page = 1, limit = 10, category, search } = req.query;
    const user = await User.findById(req.user.userId);
    
    let query = { isActive: true };
    
    if (category) query.category = category;
    if (search) {
      query.$or = [
        { title: { $regex: search, $options: 'i' } },
        { description: { $regex: search, $options: 'i' } },
        { tags: { $in: [new RegExp(search, 'i')] } }
      ];
    }
    
    const content = await Content.find(query)
      .sort({ createdAt: -1 })
      .limit(limit * 1)
      .skip((page - 1) * limit)
      .select('-__v');
    
    // Calculate personalized coin rewards based on user level
    const personalizedContent = content.map(item => ({
      ...item.toObject(),
      coinReward: Math.floor(item.coinReward * (1 + (user.level - 1) * 0.1))
    }));
    
    res.json({
      content: personalizedContent,
      pagination: {
        currentPage: page,
        totalPages: Math.ceil(await Content.countDocuments(query) / limit)
      }
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get content by ID
app.get('/api/content/:id', authenticateToken, async (req, res) => {
  try {
    const content = await Content.findById(req.params.id);
    if (!content) {
      return res.status(404).json({ error: 'Content not found' });
    }
    
    // Increment views
    content.views += 1;
    await content.save();
    
    res.json(content);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// WATCH SESSION ENDPOINTS

// Start watch session
app.post('/api/watch/start', authenticateToken, async (req, res) => {
  try {
    const { contentId, deviceType, quality } = req.body;
    
    const content = await Content.findById(contentId);
    if (!content) {
      return res.status(404).json({ error: 'Content not found' });
    }
    
    const session = new WatchSession({
      userId: req.user.userId,
      contentId,
      startTime: new Date(),
      deviceType,
      quality: quality || '720p',
      ipAddress: req.ip
    });
    
    await session.save();
    
    res.json({
      message: 'Watch session started',
      sessionId: session._id,
      content: {
        title: content.title,
        duration: content.duration,
        coinReward: content.coinReward
      }
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Update watch session (called every minute)
app.post('/api/watch/update', authenticateToken, async (req, res) => {
  try {
    const { sessionId, watchDuration, adsShown, adClicks } = req.body;
    
    const session = await WatchSession.findById(sessionId);
    if (!session) {
      return res.status(404).json({ error: 'Session not found' });
    }
    
    if (session.userId.toString() !== req.user.userId) {
      return res.status(403).json({ error: 'Unauthorized' });
    }
    
    // Update session
    session.watchDuration = watchDuration;
    session.adsShown = adsShown || 0;
    session.adClicks = adClicks || 0;
    
    // Calculate earnings
    const content = await Content.findById(session.contentId);
    const baseCoinsPerMinute = content.coinReward / content.duration;
    const coinsEarned = Math.floor(watchDuration * baseCoinsPerMinute);
    
    session.coinsEarned = coinsEarned;
    
    // Calculate your revenue (owner earnings)
    const adRevenue = (adsShown * 0.02) + (adClicks * 0.1); // $0.02 per ad view, $0.10 per click
    const engagementRevenue = watchDuration * 0.001; // $0.001 per minute watched
    session.ownerRevenue = adRevenue + engagementRevenue;
    
    await session.save();
    
    // Update user stats
    await User.findByIdAndUpdate(req.user.userId, {
      $inc: {
        coins: coinsEarned,
        totalWatchTime: watchDuration
      },
      lastActive: new Date()
    });
    
    res.json({
      message: 'Session updated',
      coinsEarned,
      totalWatchTime: watchDuration,
      ownerRevenue: session.ownerRevenue
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// End watch session
app.post('/api/watch/end', authenticateToken, async (req, res) => {
  try {
    const { sessionId } = req.body;
    
    const session = await WatchSession.findById(sessionId);
    if (!session) {
      return res.status(404).json({ error: 'Session not found' });
    }
    
    session.endTime = new Date();
    session.completed = true;
    await session.save();
    
    // Level up logic
    const user = await User.findById(req.user.userId);
    const newLevel = Math.floor(user.totalWatchTime / 60) + 1; // Level up every hour
    
    if (newLevel > user.level) {
      user.level = newLevel;
      user.coins += newLevel * 10; // Bonus coins for leveling up
      await user.save();
    }
    
    res.json({
      message: 'Session ended',
      totalCoinsEarned: session.coinsEarned,
      newLevel: user.level,
      levelUpBonus: newLevel > user.level ? newLevel * 10 : 0
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// AD ENDPOINTS

// Serve ads
app.get('/api/ads', authenticateToken, async (req, res) => {
  try {
    const { category, count = 1 } = req.query;
    const user = await User.findById(req.user.userId);
    
    let query = { isActive: true, budget: { $gt: 0 } };
    
    if (category) query.category = category;
    
    // Personalized ads based on user preferences
    if (user.adPreferences && user.adPreferences.categories.length > 0) {
      query.category = { $in: user.adPreferences.categories };
    }
    
    const ads = await Ad.find(query)
      .sort({ costPerView: -1 }) // Prioritize higher paying ads
      .limit(parseInt(count));
    
    res.json({ ads });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Track ad interaction
app.post('/api/ads/interact', authenticateToken, async (req, res) => {
  try {
    const { adId, type, sessionId } = req.body; // type: 'view' or 'click'
    
    const ad = await Ad.findById(adId);
    if (!ad) {
      return res.status(404).json({ error: 'Ad not found' });
    }
    
    if (type === 'view') {
      ad.views += 1;
      ad.budget -= ad.costPerView;
      
      // Reward user with coins
      await User.findByIdAndUpdate(req.user.userId, {
        $inc: { coins: 2 }
      });
    } else if (type === 'click') {
      ad.clicks += 1;
      ad.budget -= ad.costPerClick;
      
      // Reward user with more coins
      await User.findByIdAndUpdate(req.user.userId, {
        $inc: { coins: 5 }
      });
    }
    
    await ad.save();
    
    res.json({
      message: 'Ad interaction tracked',
      coinsEarned: type === 'view' ? 2 : 5
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// USER ENDPOINTS

// Get user profile
app.get('/api/user/profile', authenticateToken, async (req, res) => {
  try {
    const user = await User.findById(req.user.userId).select('-password');
    const totalSessions = await WatchSession.countDocuments({ userId: req.user.userId });
    const totalEarnings = await WatchSession.aggregate([
      { $match: { userId: mongoose.Types.ObjectId(req.user.userId) } },
      { $group: { _id: null, total: { $sum: '$coinsEarned' } } }
    ]);
    
    res.json({
      user,
      stats: {
        totalSessions,
        totalEarnings: totalEarnings[0]?.total || 0,
        averageSessionDuration: user.totalWatchTime / totalSessions || 0
      }
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Update user preferences
app.put('/api/user/preferences', authenticateToken, async (req, res) => {
  try {
    const { adPreferences, deviceInfo } = req.body;
    
    const user = await User.findByIdAndUpdate(
      req.user.userId,
      { adPreferences, deviceInfo },
      { new: true }
    ).select('-password');
    
    res.json({ message: 'Preferences updated', user });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// WITHDRAWAL ENDPOINTS

// Request withdrawal
app.post('/api/withdrawal/request', authenticateToken, async (req, res) => {
  try {
    const { amount, method, details } = req.body;
    
    const user = await User.findById(req.user.userId);
    if (user.coins < amount) {
      return res.status(400).json({ error: 'Insufficient coins' });
    }
    
    if (amount < 1000) {
      return res.status(400).json({ error: 'Minimum withdrawal is 1000 coins' });
    }
    
    const withdrawal = new Withdrawal({
      userId: req.user.userId,
      amount,
      method,
      details
    });
    
    await withdrawal.save();
    
    // Deduct coins from user
    user.coins -= amount;
    await user.save();
    
    res.json({
      message: 'Withdrawal request submitted',
      withdrawalId: withdrawal._id,
      remainingCoins: user.coins
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// ADMIN ENDPOINTS (Owner/Admin only)

// Get revenue dashboard
app.get('/api/admin/revenue', async (req, res) => {
  try {
    const { startDate, endDate } = req.query;
    
    const dateFilter = {};
    if (startDate) dateFilter.$gte = new Date(startDate);
    if (endDate) dateFilter.$lte = new Date(endDate);
    
    const pipeline = [
      { $match: dateFilter.createdAt ? { createdAt: dateFilter } : {} },
      {
        $group: {
          _id: null,
          totalRevenue: { $sum: '$ownerRevenue' },
          totalSessions: { $sum: 1 },
          totalWatchTime: { $sum: '$watchDuration' },
          totalAdViews: { $sum: '$adsShown' },
          totalAdClicks: { $sum: '$adClicks' }
        }
      }
    ];
    
    const revenueData = await WatchSession.aggregate(pipeline);
    const activeUsers = await User.countDocuments({ 
      lastActive: { $gte: new Date(Date.now() - 24 * 60 * 60 * 1000) }
    });
    
    res.json({
      revenue: revenueData[0] || {
        totalRevenue: 0,
        totalSessions: 0,
        totalWatchTime: 0,
        totalAdViews: 0,
        totalAdClicks: 0
      },
      activeUsers,
      revenuePerMinute: revenueData[0]?.totalRevenue / revenueData[0]?.totalWatchTime || 0,
      averageSessionDuration: revenueData[0]?.totalWatchTime / revenueData[0]?.totalSessions || 0
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Add content (admin)
app.post('/api/admin/content', async (req, res) => {
  try {
    const content = new Content(req.body);
    await content.save();
    res.json({ message: 'Content added successfully', content });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Add advertisement (admin)
app.post('/api/admin/ads', async (req, res) => {
  try {
    const ad = new Ad(req.body);
    await ad.save();
    res.json({ message: 'Ad added successfully', ad });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Daily revenue tracking (automated)
cron.schedule('0 0 * * *', async () => {
  try {
    const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000);
    const startOfDay = new Date(yesterday.setHours(0, 0, 0, 0));
    const endOfDay = new Date(yesterday.setHours(23, 59, 59, 999));
    
    const dailyStats = await WatchSession.aggregate([
      {
        $match: {
          createdAt: { $gte: startOfDay, $lte: endOfDay }
        }
      },
      {
        $group: {
          _id: null,
          totalRevenue: { $sum: '$ownerRevenue' },
          totalWatchTime: { $sum: '$watchDuration' },
          totalAdViews: { $sum: '$adsShown' },
          totalAdClicks: { $sum: '$adClicks' },
          sessionCount: { $sum: 1 }
        }
      }
    ]);
    
    const activeUsers = await User.countDocuments({
      lastActive: { $gte: startOfDay, $lte: endOfDay }
    });
    
    const stats = dailyStats[0] || {
      totalRevenue: 0,
      totalWatchTime: 0,
      totalAdViews: 0,
      totalAdClicks: 0,
      sessionCount: 0
    };
    
    const revenue = new Revenue({
      date: startOfDay,
      adRevenue: stats.totalRevenue,
      totalActiveUsers: activeUsers,
      totalWatchTime: stats.totalWatchTime,
      totalAdViews: stats.totalAdViews,
      totalAdClicks: stats.totalAdClicks,
      averageSessionDuration: stats.totalWatchTime / stats.sessionCount || 0
    });
    
    await revenue.save();
    console.log('Daily revenue tracking completed');
  } catch (error) {
    console.error('Daily revenue tracking error:', error);
  }
});

// Real-time user activity tracking
app.post('/api/user/ping', authenticateToken, async (req, res) => {
  try {
    await User.findByIdAndUpdate(req.user.userId, {
      lastActive: new Date()
    });
    res.json({ message: 'Activity tracked' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get leaderboard
app.get('/api/leaderboard', authenticateToken, async (req, res) => {
  try {
    const topUsers = await User.find()
      .sort({ totalWatchTime: -1 })
      .limit(10)
      .select('username totalWatchTime level coins');
    
    res.json({ leaderboard: topUsers });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Error handling middleware
app.use((error, req, res, next) => {
  console.error(error.stack);
  res.status(500).json({ error: 'Something went wrong!' });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Watch & Earn Backend running on port ${PORT}`);
  console.log('Revenue streams active:');
  console.log('- Ad revenue: $0.02 per view, $0.10 per click');
  console.log('- Engagement revenue: $0.001 per minute watched');
  console.log('- User activity tracking enabled');
});

module.exports = app;
